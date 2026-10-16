"""Tests for resuming a comic at the page where reading last left off."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from cdisplayagain import (
    ComicViewer,
    _load_resume_records,
    _resume_store_path,
    resume_page_index,
    save_resume_index,
)


def _viewer(tk_root, comic_path: Path, page_count: int) -> ComicViewer:
    """Build a ComicViewer backed by a fake page source of the given size."""
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), color="red").save(buffer, format="PNG")
    source = Mock()
    source.pages = [f"page{i}.jpg" for i in range(1, page_count + 1)]
    source.cleanup = None
    source.get_bytes.return_value = buffer.getvalue()
    with patch("cdisplayagain.load_comic", return_value=source):
        return ComicViewer(tk_root, comic_path)


def _write_records(records: object) -> None:
    store = _resume_store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(records), encoding="utf-8")


def _record_for(comic_path: Path, index: int, total: int) -> dict:
    try:
        key = str(comic_path.resolve())
    except OSError:
        key = str(comic_path.absolute())
    return {key: {"index": index, "total": total}}


def test_save_then_resume_returns_index(tmp_path):
    """A saved mid-comic page is returned when reopening."""
    comic = tmp_path / "issue1.cbz"
    save_resume_index(comic, 4, 10)
    assert resume_page_index(comic, 10) == 4


def test_missing_store_resumes_first_page(tmp_path):
    """An unknown comic starts from the first page."""
    assert resume_page_index(tmp_path / "never.cbz", 10) is None


def test_first_page_is_not_resumed(tmp_path):
    """A saved first page still reports no resume target."""
    comic = tmp_path / "issue1.cbz"
    save_resume_index(comic, 0, 10)
    assert resume_page_index(comic, 10) is None


def test_saving_last_page_clears_position(tmp_path):
    """Finishing a comic removes its saved position."""
    comic = tmp_path / "issue1.cbz"
    save_resume_index(comic, 4, 10)
    save_resume_index(comic, 9, 10)
    assert resume_page_index(comic, 10) is None
    assert _load_resume_records() == {}


def test_recorded_last_page_is_not_resumed(tmp_path):
    """A stored final page is treated as finished rather than resumed."""
    comic = tmp_path / "issue1.cbz"
    _write_records(_record_for(comic, 9, 10))
    assert resume_page_index(comic, 10) is None


def test_single_page_comic_never_resumes(tmp_path):
    """A single-page comic has no meaningful position to restore."""
    comic = tmp_path / "one.cbz"
    save_resume_index(comic, 0, 1)
    assert resume_page_index(comic, 1) is None
    assert _load_resume_records() == {}


def test_corrupt_store_is_ignored(tmp_path):
    """Malformed state files fall back to the first page."""
    store = _resume_store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text("{not json", encoding="utf-8")
    assert _load_resume_records() == {}
    assert resume_page_index(tmp_path / "issue.cbz", 10) is None


def test_non_dict_store_is_ignored(tmp_path):
    """A state file that is not a JSON object is ignored."""
    _write_records([1, 2, 3])
    assert _load_resume_records() == {}


def test_read_failure_is_ignored(tmp_path, monkeypatch):
    """Unreadable state files do not crash the reader."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "resume.json").mkdir()
    monkeypatch.setenv("CDISPLAYAGAIN_STATE_DIR", str(state_dir))
    assert _load_resume_records() == {}


def test_non_dict_record_is_ignored(tmp_path):
    """A malformed per-comic record is ignored."""
    comic = tmp_path / "issue.cbz"
    _write_records({str(comic.resolve()): "oops"})
    assert resume_page_index(comic, 10) is None


def test_non_integer_index_is_ignored(tmp_path):
    """A record without an integer index is ignored."""
    comic = tmp_path / "issue.cbz"
    _write_records({str(comic.resolve()): {"index": "two", "total": 10}})
    assert resume_page_index(comic, 10) is None


def test_index_out_of_range_is_not_resumed(tmp_path):
    """A position beyond a shortened comic is not resumed."""
    comic = tmp_path / "issue.cbz"
    _write_records(_record_for(comic, 12, 20))
    assert resume_page_index(comic, 5) is None


def test_resolve_failure_falls_back_to_absolute(tmp_path):
    """A path that cannot be resolved still produces a usable key."""
    with patch.object(Path, "resolve", side_effect=OSError):
        assert resume_page_index(tmp_path / "issue.cbz", 10) is None


def test_write_failure_is_swallowed(tmp_path, monkeypatch):
    """An unwritable state directory does not raise."""
    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")
    monkeypatch.setenv("CDISPLAYAGAIN_STATE_DIR", str(blocker / "state"))
    save_resume_index(tmp_path / "issue.cbz", 3, 10)
    assert _load_resume_records() == {}


def test_store_uses_env_override(tmp_path, monkeypatch):
    """The state directory honours the environment override."""
    target = tmp_path / "custom"
    monkeypatch.setenv("CDISPLAYAGAIN_STATE_DIR", str(target))
    assert _resume_store_path() == target / "resume.json"


@pytest.mark.skipif(sys.platform == "darwin", reason="uses XDG state path")
def test_store_defaults_to_xdg_state(tmp_path, monkeypatch):
    """Without an override the state lives under the XDG state directory."""
    monkeypatch.delenv("CDISPLAYAGAIN_STATE_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert _resume_store_path() == tmp_path / "xdg" / "cdisplayagain" / "resume.json"


def test_open_comic_resumes_saved_page(tk_root, tmp_path):
    """Opening a comic lands on the remembered page."""
    comic = tmp_path / "issue.cbz"
    save_resume_index(comic, 4, 10)
    app = _viewer(tk_root, comic, 10)
    assert app._current_index == 4


def test_open_comic_starts_at_first_when_finished(tk_root, tmp_path):
    """A comic left on its final page reopens at the beginning."""
    comic = tmp_path / "issue.cbz"
    _write_records(_record_for(comic, 9, 10))
    app = _viewer(tk_root, comic, 10)
    assert app._current_index == 0


def test_navigation_saves_position(tk_root, tmp_path):
    """Page turns update the remembered position."""
    comic = tmp_path / "issue.cbz"
    app = _viewer(tk_root, comic, 10)
    app.next_page()
    assert resume_page_index(comic, 10) == 1
    app.prev_page()
    assert resume_page_index(comic, 10) is None


def test_reaching_last_page_clears_position(tk_root, tmp_path):
    """Jumping to the final page clears the saved position."""
    comic = tmp_path / "issue.cbz"
    app = _viewer(tk_root, comic, 10)
    app._current_index = 5
    app._save_resume_position()
    assert resume_page_index(comic, 10) == 5
    app.last_page()
    assert resume_page_index(comic, 10) is None


def test_switching_comic_records_previous_position(tk_root, tmp_path):
    """Opening another comic saves the current one's position first."""
    first = tmp_path / "a.cbz"
    second = tmp_path / "b.cbz"
    other = Mock(pages=["only.jpg"], cleanup=None)
    other.get_bytes.return_value = b""
    app = _viewer(tk_root, first, 10)
    app._current_index = 3
    with patch("cdisplayagain.load_comic", return_value=other):
        app._open_comic(second)
    assert resume_page_index(first, 10) == 3
    assert app._current_index == 0


def test_destroy_records_position(tk_root, tmp_path):
    """Destroying the viewer persists the current page."""
    comic = tmp_path / "issue.cbz"
    app = _viewer(tk_root, comic, 10)
    app._current_index = 6
    app._on_destroy(Mock(widget=app))
    assert resume_page_index(comic, 10) == 6


def test_save_position_without_pages_is_noop(tk_root, tmp_path):
    """Saving with an empty source leaves the store untouched."""
    comic = tmp_path / "issue.cbz"
    app = _viewer(tk_root, comic, 5)
    app.source = Mock(pages=[])
    app._save_resume_position()
    assert _load_resume_records() == {}
