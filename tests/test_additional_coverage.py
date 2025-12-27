"""Additional coverage tests for remaining paths."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_preload_with_no_app(tk_root, tmp_path):
    """Test ImageWorker.preload returns early when app is None."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._worker._app = None
    viewer._worker.preload(0)


def test_trigger_space(tk_root, tmp_path):
    """Test _trigger_space debounces space advance."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._trigger_space()
    assert viewer._nav_debounce._timer_id is not None


def test_log_key_event(tk_root, tmp_path):
    """Test _log_key_event logs key event details."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    event = type(
        "Event",
        (),
        {"keysym": "Right", "char": "", "keycode": 65, "state": 0, "widget": viewer.canvas},
    )()
    viewer._log_key_event(event)


def test_cancel_active_dialog_tclerror(tk_root, tmp_path, caplog):
    """Test _cancel_active_dialog handles TclError gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    with caplog.at_level(logging.INFO):
        viewer._cancel_active_dialog()


def test_find_next_image_index_with_no_source(tk_root, tmp_path):
    """Test _find_next_image_index returns None when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    result = viewer._find_next_image_index(0)
    assert result is None


def test_render_current_sync_with_no_source(tk_root, tmp_path):
    """Test _render_current_sync returns early when no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    viewer._render_current_sync()


def test_display_cached_image_imagetk_fallback(tk_root, tmp_path):
    """Test _display_cached_image falls back to photoimage_from_pil on ImageTk error."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._imagetk_ready = True

    with patch("cdisplayagain.ImageTk.PhotoImage", side_effect=RuntimeError("ImageTk error")):
        viewer._display_cached_image(img)
    assert viewer._imagetk_ready is False
    assert viewer._tk_img is not None


def test_display_cached_image_without_imagetk(tk_root, tmp_path):
    """Test _display_cached_image uses photoimage_from_pil when ImageTk not ready."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._imagetk_ready = False
    viewer._display_cached_image(img)
    assert viewer._tk_img is not None


def test_display_image_fast_imagetk_fallback(tk_root, tmp_path):
    """Test _display_image_fast falls back to photoimage_from_pil on ImageTk error."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._imagetk_ready = True

    with patch("cdisplayagain.ImageTk.PhotoImage", side_effect=RuntimeError("ImageTk error")):
        viewer._display_image_fast(img)
    assert viewer._imagetk_ready is False
    assert viewer._tk_img is not None


def test_display_image_fast_without_imagetk(tk_root, tmp_path):
    """Test _display_image_fast uses photoimage_from_pil when ImageTk not ready."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._imagetk_ready = False
    viewer._display_image_fast(img)
    assert viewer._tk_img is not None


def test_display_image_fast_clamps_offset_positive(tk_root, tmp_path):
    """Test _display_image_fast clamps positive scroll offset."""
    _write_image(tmp_path / "page1.png", size=(100, 200))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (100, 200))
    viewer._scroll_offset = 1000
    viewer._display_image_fast(img)
    assert viewer._scroll_offset <= max(0, 200 - viewer.canvas.winfo_height())


def test_display_image_fast_clamps_offset_negative(tk_root, tmp_path):
    """Test _display_image_fast clamps negative scroll offset."""
    _write_image(tmp_path / "page1.png", size=(100, 200))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (100, 200))
    viewer._scroll_offset = -100
    viewer._display_image_fast(img)
    assert viewer._scroll_offset >= 0


def test_set_background_color_with_empty_string(tk_root, tmp_path):
    """Test set_background_color handles empty color string."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    initial_color = viewer._background_color
    viewer.set_background_color("")
    assert viewer._background_color == initial_color


def test_space_advance_without_scaled_size(tk_root, tmp_path):
    """Test _space_advance goes to next page when no scaled size."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._scaled_size = None

    initial_index = viewer._current_index
    viewer._space_advance()
    assert viewer._current_index != initial_index


def test_space_advance_at_max_offset(tk_root, tmp_path):
    """Test _space_advance goes to next page at max scroll offset."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", size=(100, 500))
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    ch = max(1, viewer.canvas.winfo_height())
    max_offset = max(0, 500 - ch)
    viewer._scroll_offset = max_offset

    viewer._space_advance()
    assert viewer._current_index == 1


def test_space_advance_near_max_offset(tk_root, tmp_path):
    """Test _space_advance scrolls to max offset then next page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", size=(100, 500))
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    ch = max(1, viewer.canvas.winfo_height())
    max_offset = max(0, 500 - ch)
    viewer._scroll_offset = max_offset - 200

    viewer._space_advance()
    assert viewer._scroll_offset == max_offset or viewer._current_index == 1


def test_reposition_image_clamps_offset_at_bottom(tk_root, tmp_path):
    """Test _reposition_current_image clamps offset at bottom."""
    _write_image(tmp_path / "page1.png", size=(100, 500))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    ch = max(1, viewer.canvas.winfo_height())
    from PIL import Image

    img = Image.new("RGB", (100, 500))
    viewer._display_cached_image(img)

    viewer._reposition_current_image()
    assert viewer._scroll_offset <= max(0, 500 - ch)


def test_on_canvas_configure_with_small_dimensions(tk_root, tmp_path):
    """Test _on_canvas_configure ignores small dimensions."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    event = type("Event", (), {"width": 50, "height": 50})()
    viewer._on_canvas_configure(event)
    assert viewer._first_render_done is False


def test_show_info_overlay_with_no_source(tk_root, tmp_path):
    """Test _show_info_overlay returns early with no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    viewer._show_info_overlay("info.txt")
    assert viewer._info_overlay is None


def test_show_info_overlay_with_existing_overlay(tk_root, tmp_path):
    """Test _show_info_overlay returns early with existing overlay."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._info_overlay = tk.Label(tk_root, text="existing")
    initial_overlay = viewer._info_overlay
    viewer._show_info_overlay("new.txt")
    assert viewer._info_overlay is initial_overlay


def test_execute_page_change(tk_root, tmp_path):
    """Test _execute_page_change executes action."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    executed = [False]

    def test_action():
        executed[0] = True

    viewer._execute_page_change(test_action)
    assert executed[0] is True


def test_open_comic_cleanup_handles_errors(tk_root, tmp_path, caplog):
    """Test _open_comic handles cleanup errors."""
    _write_image(tmp_path / "page1.png")
    _write_image(tmp_path / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = cdisplayagain.load_comic(tmp_path / "page1.png")

    cleanup_called = [False]

    def failing_cleanup():
        cleanup_called[0] = True
        raise RuntimeError("cleanup error")

    if viewer.source:
        viewer.source.cleanup = failing_cleanup

    with caplog.at_level(logging.WARNING):
        viewer._open_comic(tmp_path / "page2.png")
        assert cleanup_called[0]
        assert any("Cleanup failed" in record.message for record in caplog.records)
