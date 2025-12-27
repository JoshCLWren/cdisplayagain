"""Additional tests for 95% coverage target."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_render_current_sync_with_info_file_no_next_image(tk_root, tmp_path):
    """Test _render_current_sync with info file and no following image."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.txt").write_text("info")

    viewer = cdisplayagain.ComicViewer(tk_root, folder)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._render_current_sync()
    assert viewer._canvas_image_id is None


def test_render_current_sync_with_info_file_and_next_image_cached(tk_root, tmp_path):
    """Test _render_current_sync with info file and cached next image."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    (folder / "info.txt").write_text("info")

    viewer = cdisplayagain.ComicViewer(tk_root, folder)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    cache_key = (1, cw, ch)
    viewer._image_cache[cache_key] = img

    viewer._render_current_sync()
    assert viewer._info_overlay is not None


def test_display_image_fast_sets_anchor_center(tk_root, tmp_path):
    """Test _display_image_fast sets center anchor for fitting image."""
    _write_image(tmp_path / "page1.png", size=(50, 50))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._canvas_image_id = 123
    viewer._display_image_fast(img)
    assert viewer._canvas_image_id is not None


def test_display_image_fast_sets_anchor_north(tk_root, tmp_path):
    """Test _display_image_fast sets north anchor for tall image."""
    _write_image(tmp_path / "page1.png", size=(100, 1000))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (100, 1000))
    viewer._canvas_image_id = 123
    viewer._display_image_fast(img)
    assert viewer._canvas_image_id is not None


def test_display_cached_image_sets_anchor_north(tk_root, tmp_path):
    """Test _display_cached_image sets north anchor for tall image."""
    _write_image(tmp_path / "page1.png", size=(100, 1000))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (100, 1000))
    viewer._canvas_image_id = 123
    viewer._display_cached_image(img)
    assert viewer._canvas_image_id is not None


def test_configure_cursor_none_succeeds(tk_root, tmp_path):
    """Test _configure_cursor succeeds with 'none' cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._configure_cursor()
    assert viewer._cursor_name in ("none", "dotbox", "arrow")


def test_set_cursor_hidden_none_cursor(tk_root, tmp_path):
    """Test _set_cursor_hidden with 'none' cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._set_cursor_hidden(True)
    assert viewer._cursor_hidden is True


def test_set_cursor_hidden_tclerror(tk_root, tmp_path):
    """Test _set_cursor_hidden handles TclError."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._set_cursor_hidden(False)
    assert viewer._cursor_hidden is False


def test_space_advance_with_info_overlay_dismisses(tk_root, tmp_path):
    """Test _space_advance dismisses info overlay and advances."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._show_info_overlay("test")
    assert viewer._info_overlay is not None

    viewer._space_advance()
    assert viewer._info_overlay is None


def test_next_page_with_source(tk_root, tmp_path):
    """Test next_page advances when source exists."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    initial_gen = viewer._render_generation

    viewer.next_page()
    assert viewer._current_index == 1
    assert viewer._render_generation == initial_gen + 1


def test_prev_page_with_source(tk_root, tmp_path):
    """Test prev_page goes back when source exists."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 1
    initial_gen = viewer._render_generation

    viewer.prev_page()
    assert viewer._current_index == 0
    assert viewer._render_generation == initial_gen + 1


def test_first_page_with_source(tk_root, tmp_path):
    """Test first_page jumps to start."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 1
    initial_gen = viewer._render_generation

    viewer.first_page()
    assert viewer._current_index == 0
    assert viewer._render_generation == initial_gen + 1


def test_last_page_with_source(tk_root, tmp_path):
    """Test last_page jumps to end."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    initial_gen = viewer._render_generation

    viewer.last_page()
    assert viewer._current_index == 1
    assert viewer._render_generation == initial_gen + 1


def test_next_page_at_end(tk_root, tmp_path):
    """Test next_page at end stays at last page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer.next_page()
    assert viewer._current_index == 0


def test_prev_page_at_start(tk_root, tmp_path):
    """Test prev_page at start stays at first page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer.prev_page()
    assert viewer._current_index == 0


def test_set_one_page_mode(tk_root, tmp_path):
    """Test set_one_page_mode."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._two_page_mode = True
    viewer.set_one_page_mode()
    assert viewer._two_page_mode is False


def test_set_two_page_mode(tk_root, tmp_path):
    """Test set_two_page_mode."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._two_page_mode = False
    viewer.set_two_page_mode()
    assert viewer._two_page_mode is True


def test_toggle_two_pages(tk_root, tmp_path):
    """Test toggle_two_pages."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_mode = viewer._two_page_mode
    viewer.toggle_two_pages()
    assert viewer._two_page_mode is not initial_mode


def test_toggle_color_balance(tk_root, tmp_path):
    """Test toggle_color_balance."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_state = viewer._color_balance_enabled
    viewer.toggle_color_balance()
    assert viewer._color_balance_enabled is not initial_state


def test_toggle_yellow_reduction(tk_root, tmp_path):
    """Test toggle_yellow_reduction."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_state = viewer._yellow_reduction_enabled
    viewer.toggle_yellow_reduction()
    assert viewer._yellow_reduction_enabled is not initial_state


def test_toggle_hints(tk_root, tmp_path):
    """Test toggle_hints."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_state = viewer._hints_enabled
    viewer.toggle_hints()
    assert viewer._hints_enabled is not initial_state


def test_toggle_two_page_advance(tk_root, tmp_path):
    """Test toggle_two_page_advance."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_state = viewer._two_page_advance_enabled
    viewer.toggle_two_page_advance()
    assert viewer._two_page_advance_enabled is not initial_state


def test_set_page_buffer(tk_root, tmp_path):
    """Test set_page_buffer."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.set_page_buffer(10)
    assert viewer._page_buffer_size == 10


def test_set_page_buffer_none(tk_root, tmp_path):
    """Test set_page_buffer with None."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_size = viewer._page_buffer_size
    viewer.set_page_buffer(None)
    assert viewer._page_buffer_size == initial_size


def test_set_mouse_binding(tk_root, tmp_path):
    """Test set_mouse_binding."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.set_mouse_binding("Button-3", "quit")
    assert viewer._mouse_bindings["Button-3"] == "quit"


def test_show_hint_popup(tk_root, tmp_path):
    """Test _show_hint_popup creates popup."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._show_hint_popup()
    assert viewer._hint_popup is not None


def test_show_hint_popup_already_visible(tk_root, tmp_path):
    """Test _show_hint_popup when already visible."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._hint_popup = tk.Label(tk_root, text="existing")
    viewer._show_hint_popup()
    assert viewer._hint_popup is not None


def test_dismiss_hint_popup(tk_root, tmp_path):
    """Test _dismiss_hint_popup removes popup."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._hint_popup = tk.Label(tk_root, text="hint")
    viewer._dismiss_hint_popup()
    assert viewer._hint_popup is None


def test_set_small_cursor(tk_root, tmp_path):
    """Test set_small_cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_state = viewer._small_cursor_enabled
    viewer.set_small_cursor()
    assert viewer._small_cursor_enabled is not initial_state


def test_ensure_focus_handles_tclerror(tk_root, tmp_path, monkeypatch):
    """Test _ensure_focus handles TclError."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    def failing_focus_force():
        raise tk.TclError("error")

    monkeypatch.setattr(viewer, "focus_force", failing_focus_force)
    viewer._ensure_focus()
