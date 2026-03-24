"""Tests for sequential reading (sibling comic navigation) feature."""

import io
import tkinter as tk
import zipfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from cdisplayagain import ComicViewer, _as_wm, get_sibling_comics


def _create_test_cbz(path: Path, num_pages: int = 1) -> None:
    """Create a minimal valid .cbz archive with the given number of pages."""
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(num_pages):
            img = Image.new("RGB", (10, 10), color="red")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page{i}.png", buf.getvalue())


def _make_valid_image_bytes() -> bytes:
    """Return valid PNG image bytes for mocking."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_mock_image(valid_image_bytes: bytes) -> Mock:
    """Create a mock PIL Image with standard attributes."""
    mock_img = Mock()
    mock_img.mode = "RGB"
    mock_img.size = (100, 100)
    mock_img.resize.return_value = mock_img
    mock_img.convert.return_value = mock_img
    mock_img.save = lambda b, **kwargs: b.write(valid_image_bytes)
    return mock_img


@pytest.fixture
def comic_viewer(tk_root: tk.Tk) -> Generator[ComicViewer]:
    """Create a ComicViewer with mocked dependencies."""
    valid_bytes = _make_valid_image_bytes()
    mock_source = Mock()
    mock_source.pages = ["page0.png", "page1.png", "page2.png"]
    mock_source.cleanup = None
    mock_source.get_bytes.return_value = valid_bytes

    mock_img = _make_mock_image(valid_bytes)

    with (
        patch("cdisplayagain.load_comic", return_value=mock_source),
        patch("PIL.Image.open", return_value=mock_img),
        patch("tkinter.messagebox.showerror"),
        patch("tkinter.messagebox.showinfo"),
        patch("tkinter.filedialog.askopenfilename"),
        patch("tkinter.filedialog.askopenfilenames"),
    ):
        app = ComicViewer(tk_root, Path("dummy.cbz"))
        tk_root.update()
        yield app


# --- get_sibling_comics tests (pure function, no Tk needed) ---


def test_get_sibling_comics_multiple_archives(tmp_path: Path) -> None:
    """Directory with 3 .cbz files returns sorted list and correct index."""
    _create_test_cbz(tmp_path / "alpha.cbz")
    _create_test_cbz(tmp_path / "beta.cbz")
    _create_test_cbz(tmp_path / "gamma.cbz")

    siblings, index = get_sibling_comics(tmp_path / "beta.cbz")

    assert len(siblings) == 3
    assert index == 1
    assert siblings[0].name == "alpha.cbz"
    assert siblings[1].name == "beta.cbz"
    assert siblings[2].name == "gamma.cbz"


def test_get_sibling_comics_natural_sort_order(tmp_path: Path) -> None:
    """Natural sort puts issue2 before issue10."""
    _create_test_cbz(tmp_path / "issue10.cbz")
    _create_test_cbz(tmp_path / "issue2.cbz")
    _create_test_cbz(tmp_path / "issue1.cbz")

    siblings, index = get_sibling_comics(tmp_path / "issue2.cbz")

    assert [s.name for s in siblings] == ["issue1.cbz", "issue2.cbz", "issue10.cbz"]
    assert index == 1


def test_get_sibling_comics_mixed_extensions(tmp_path: Path) -> None:
    """Archive extensions (.cbz, .cbr, .tar) included; .txt, .jpg excluded."""
    _create_test_cbz(tmp_path / "comic.cbz")
    _create_test_cbz(tmp_path / "comic.cbr")
    _create_test_cbz(tmp_path / "comic.tar")
    (tmp_path / "readme.txt").write_text("hello")
    img = Image.new("RGB", (10, 10))
    img.save(tmp_path / "cover.jpg")

    siblings, index = get_sibling_comics(tmp_path / "comic.cbz")

    names = {s.name for s in siblings}
    assert "comic.cbz" in names
    assert "comic.cbr" in names
    assert "comic.tar" in names
    assert "readme.txt" not in names
    assert "cover.jpg" not in names
    assert len(siblings) == 3


def test_get_sibling_comics_single_archive(tmp_path: Path) -> None:
    """Single archive in directory returns list of 1 and index 0."""
    _create_test_cbz(tmp_path / "only.cbz")

    siblings, index = get_sibling_comics(tmp_path / "only.cbz")

    assert len(siblings) == 1
    assert index == 0
    assert siblings[0].name == "only.cbz"


def test_get_sibling_comics_non_archive_file(tmp_path: Path) -> None:
    """Non-archive extension (.png) returns ([], -1)."""
    img = Image.new("RGB", (10, 10))
    img.save(tmp_path / "image.png")

    siblings, index = get_sibling_comics(tmp_path / "image.png")

    assert siblings == []
    assert index == -1


def test_get_sibling_comics_directory_path(tmp_path: Path) -> None:
    """Directory path returns ([], -1) since suffix won't match."""
    subdir = tmp_path / "comics"
    subdir.mkdir()

    siblings, index = get_sibling_comics(subdir)

    assert siblings == []
    assert index == -1


def test_get_sibling_comics_empty_directory_no_archives(tmp_path: Path) -> None:
    """Directory with only non-archive files: archive path not found returns ([], -1)."""
    (tmp_path / "readme.txt").write_text("hello")
    fake_cbz = tmp_path / "missing.cbz"
    fake_cbz.write_bytes(b"fake")

    siblings, index = get_sibling_comics(fake_cbz)

    assert len(siblings) == 1
    assert index == 0


def test_get_sibling_comics_permission_error(tmp_path: Path) -> None:
    """OSError during iterdir returns ([], -1)."""
    cbz_path = tmp_path / "test.cbz"
    _create_test_cbz(cbz_path)

    with patch.object(type(cbz_path.parent), "iterdir", side_effect=OSError("denied")):
        siblings, index = get_sibling_comics(cbz_path)

    assert siblings == []
    assert index == -1


# --- ComicViewer.next_comic / prev_comic tests ---


def test_next_comic_advances(comic_viewer: ComicViewer) -> None:
    """next_comic() advances to the next sibling."""
    a, b, c = Path("a.cbz"), Path("b.cbz"), Path("c.cbz")
    comic_viewer._sibling_comics = [a, b, c]
    comic_viewer._sibling_index = 0

    with patch.object(comic_viewer, "_open_comic") as mock_open, patch.object(
        comic_viewer, "_render_current"
    ):
        comic_viewer.next_comic()

    mock_open.assert_called_once_with(b)


def test_prev_comic_goes_back(comic_viewer: ComicViewer) -> None:
    """prev_comic() moves to the previous sibling."""
    a, b, c = Path("a.cbz"), Path("b.cbz"), Path("c.cbz")
    comic_viewer._sibling_comics = [a, b, c]
    comic_viewer._sibling_index = 2

    with patch.object(comic_viewer, "_open_comic") as mock_open, patch.object(
        comic_viewer, "_render_current"
    ):
        comic_viewer.prev_comic()

    mock_open.assert_called_once_with(b)


def test_next_comic_at_end_noop(comic_viewer: ComicViewer) -> None:
    """next_comic() at last position does not call _open_comic."""
    a, b = Path("a.cbz"), Path("b.cbz")
    comic_viewer._sibling_comics = [a, b]
    comic_viewer._sibling_index = 1

    with patch.object(comic_viewer, "_open_comic") as mock_open:
        comic_viewer.next_comic()

    mock_open.assert_not_called()


def test_prev_comic_at_start_noop(comic_viewer: ComicViewer) -> None:
    """prev_comic() at first position does not call _open_comic."""
    a, b = Path("a.cbz"), Path("b.cbz")
    comic_viewer._sibling_comics = [a, b]
    comic_viewer._sibling_index = 0

    with patch.object(comic_viewer, "_open_comic") as mock_open:
        comic_viewer.prev_comic()

    mock_open.assert_not_called()


def test_next_comic_no_siblings_noop(comic_viewer: ComicViewer) -> None:
    """next_comic() with empty siblings list does not crash."""
    comic_viewer._sibling_comics = []
    comic_viewer._sibling_index = -1

    with patch.object(comic_viewer, "_open_comic") as mock_open:
        comic_viewer.next_comic()

    mock_open.assert_not_called()


def test_prev_comic_no_siblings_noop(comic_viewer: ComicViewer) -> None:
    """prev_comic() with empty siblings list does not crash."""
    comic_viewer._sibling_comics = []
    comic_viewer._sibling_index = -1

    with patch.object(comic_viewer, "_open_comic") as mock_open:
        comic_viewer.prev_comic()

    mock_open.assert_not_called()


def test_next_comic_negative_index_noop(comic_viewer: ComicViewer) -> None:
    """next_comic() with _sibling_index = -1 is a noop."""
    comic_viewer._sibling_comics = [Path("a.cbz")]
    comic_viewer._sibling_index = -1

    with patch.object(comic_viewer, "_open_comic") as mock_open:
        comic_viewer.next_comic()

    mock_open.assert_not_called()


# --- Auto-advance tests ---


def test_next_page_at_last_page_calls_next_comic(comic_viewer: ComicViewer) -> None:
    """On last page, next_page() calls next_comic()."""
    assert comic_viewer.source is not None
    comic_viewer._current_index = len(comic_viewer.source.pages) - 1

    with patch.object(comic_viewer, "next_comic") as mock_next:
        comic_viewer.next_page()

    mock_next.assert_called_once()


def test_prev_page_at_first_page_calls_prev_comic(comic_viewer: ComicViewer) -> None:
    """On first page, prev_page() calls prev_comic()."""
    comic_viewer._current_index = 0

    with patch.object(comic_viewer, "prev_comic") as mock_prev:
        comic_viewer.prev_page()

    mock_prev.assert_called_once()


def test_next_page_normal_does_not_call_next_comic(comic_viewer: ComicViewer) -> None:
    """On page 0 of 3, next_page() advances page without calling next_comic."""
    comic_viewer._current_index = 0

    with (
        patch.object(comic_viewer, "next_comic") as mock_next,
        patch.object(comic_viewer, "_render_current"),
    ):
        comic_viewer.next_page()

    mock_next.assert_not_called()
    assert comic_viewer._current_index == 1


def test_prev_page_normal_does_not_call_prev_comic(comic_viewer: ComicViewer) -> None:
    """On page 2 of 3, prev_page() goes back without calling prev_comic."""
    comic_viewer._current_index = 2

    with (
        patch.object(comic_viewer, "prev_comic") as mock_prev,
        patch.object(comic_viewer, "_render_current"),
    ):
        comic_viewer.prev_page()

    mock_prev.assert_not_called()
    assert comic_viewer._current_index == 1


# --- Keybinding tests ---


def test_n_key_binds_to_next_comic(comic_viewer: ComicViewer) -> None:
    """Verify 'n' key is bound."""
    bindings = comic_viewer.bind_all("n")
    assert bindings


def test_p_key_binds_to_prev_comic(comic_viewer: ComicViewer) -> None:
    """Verify 'p' key is bound."""
    bindings = comic_viewer.bind_all("p")
    assert bindings


# --- Context menu tests ---


def test_context_menu_has_next_and_prev_comic(comic_viewer: ComicViewer) -> None:
    """Context menu contains 'Next comic' and 'Previous comic' labels."""
    menu = comic_viewer._context_menu
    last = menu.index("end")
    assert last is not None
    labels: list[str] = []
    for i in range(last + 1):
        if menu.type(i) == "command":
            labels.append(str(menu.entrycget(i, "label")))

    assert "Next comic" in labels
    assert "Previous comic" in labels


# --- Title bar tests ---


def test_title_shows_sibling_position(comic_viewer: ComicViewer) -> None:
    """Title includes [2/5] when siblings exist."""
    comic_viewer._sibling_comics = [Path(f"{i}.cbz") for i in range(5)]
    comic_viewer._sibling_index = 1
    comic_viewer._update_title()

    title = _as_wm(comic_viewer.master).title()
    assert "[2/5]" in title


def test_title_no_prefix_without_siblings(comic_viewer: ComicViewer) -> None:
    """Title has no bracket prefix when no siblings."""
    comic_viewer._sibling_comics = []
    comic_viewer._sibling_index = -1
    comic_viewer._update_title()

    title = _as_wm(comic_viewer.master).title()
    assert "[" not in title
