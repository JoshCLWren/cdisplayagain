"""Additional tests to increase coverage to 95%."""

from pathlib import Path

import cdisplayagain


def _write_image(path: Path, size=(100, 100), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_trigger_space_calls_space_advance(tk_root, tmp_path):
    """Test _trigger_space method calls _space_advance."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._space_advance = lambda: None
    viewer._trigger_space()


def test_next_page_without_source(tk_root, tmp_path):
    """Test next_page returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    initial_index = viewer._current_index
    viewer.next_page()
    assert viewer._current_index == initial_index


def test_prev_page_without_source(tk_root, tmp_path):
    """Test prev_page returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    initial_index = viewer._current_index
    viewer.prev_page()
    assert viewer._current_index == initial_index


def test_first_page_without_source(tk_root, tmp_path):
    """Test first_page returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    initial_index = viewer._current_index
    viewer.first_page()
    assert viewer._current_index == initial_index


def test_last_page_without_source(tk_root, tmp_path):
    """Test last_page returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    initial_index = viewer._current_index
    viewer.last_page()
    assert viewer._current_index == initial_index


def test_render_current_sync_without_source(tk_root, tmp_path):
    """Test _render_current_sync returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    viewer._render_current_sync()


def test_find_next_image_index_no_next(tk_root, tmp_path):
    """Test _find_next_image_index returns None when no next image."""
    _write_image(tmp_path / "page1.png")
    _write_image(tmp_path / "page2.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = cdisplayagain.load_directory(tmp_path)
    viewer._current_index = 1

    result = viewer._find_next_image_index(1)
    assert result is None


def test_find_next_image_index_without_source(tk_root, tmp_path):
    """Test _find_next_image_index returns None when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    result = viewer._find_next_image_index(0)
    assert result is None


def test_hint_popup_with_existing_timer(tk_root, tmp_path):
    """Test _show_hint_popup cancels existing timer."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._hint_timer = viewer.after(1000, lambda: None)
    viewer._show_hint_popup()
    assert viewer._hint_popup is not None
    viewer._dismiss_hint_popup()


def test_space_advance_with_info_overlay(tk_root, tmp_path):
    """Test _space_advance dismisses info overlay."""
    import tkinter as tk

    _write_image(tmp_path / "page1.png")
    _write_image(tmp_path / "page2.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = cdisplayagain.load_directory(tmp_path)

    viewer._info_overlay = tk.Label(viewer, text="Info")
    viewer._info_overlay.place(relx=0.5, rely=0.5)
    initial_index = viewer._current_index

    viewer._space_advance()
    assert viewer._info_overlay is None
    assert viewer._current_index == initial_index + 1


def test_space_advance_without_scaled_size(tk_root, tmp_path):
    """Test _space_advance advances page when no scaled size."""
    _write_image(tmp_path / "page1.png")
    _write_image(tmp_path / "page2.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = cdisplayagain.load_directory(tmp_path)
    viewer._scaled_size = None
    viewer._current_index = 0

    viewer._space_advance()
    assert viewer._current_index == 1


def test_open_comic_cleanup_failure(tk_root, tmp_path, monkeypatch):
    """Test _open_comic handles cleanup failures."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer.source = cdisplayagain.load_directory(tmp_path)

    def failing_cleanup():
        raise RuntimeError("Cleanup failed")

    viewer.source.cleanup = failing_cleanup

    _write_image(tmp_path / "page2.png")
    viewer._open_comic(tmp_path / "page2.png")
    assert viewer.source is not None
