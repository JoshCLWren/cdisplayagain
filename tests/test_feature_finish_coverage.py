"""Targeted coverage tests for archive helpers and image reposition branches."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import archives
from cdisplayagain import ComicViewer


def _valid_png_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _viewer_with_mock_source(tk_root: tk.Tk) -> ComicViewer:
    valid = _valid_png_bytes()
    mock_source = Mock()
    mock_source.pages = ["page0.png"]
    mock_source.cleanup = None
    mock_source.get_bytes.return_value = valid

    mock_img = Mock()
    mock_img.mode = "RGB"
    mock_img.size = (100, 100)
    mock_img.resize.return_value = mock_img
    mock_img.convert.return_value = mock_img
    mock_img.save = lambda b, **kwargs: b.write(valid)

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
        return app


def test_archives_perf_log_emits_when_enabled(monkeypatch) -> None:
    """perf_log should emit a log line when PERF_LOGGING is enabled."""
    monkeypatch.setattr(archives, "PERF_LOGGING", True)
    with patch("archives.logging.info") as info:
        archives.perf_log("op", 0.1, " extra")
    info.assert_called_once()


def test_get_sibling_comics_missing_parent_dir(tmp_path: Path) -> None:
    """A missing parent directory should return the empty/no-index tuple."""
    missing_file = tmp_path / "missing" / "comic.cbz"
    siblings, index = archives.get_sibling_comics(missing_file)
    assert siblings == []
    assert index == -1


def test_display_cached_image_clamps_scroll_offset_for_tall_image(tk_root: tk.Tk) -> None:
    """Tall images should clamp scroll offset instead of overflowing."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app.canvas.config(width=120, height=100)
        app.canvas.update_idletasks()
        app._scroll_offset = 10_000

        tall = Image.new("RGB", (120, 400), color="blue")
        app._display_cached_image(tall)

        max_offset = max(0, 400 - max(1, app.canvas.winfo_height()))
        assert app._scroll_offset >= 0
        assert app._scroll_offset <= max_offset
    finally:
        app.cleanup()


def test_reposition_current_image_centers_short_image(tk_root: tk.Tk) -> None:
    """Short images should be centered vertically when repositioned."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app.canvas.config(width=120, height=200)
        app.canvas.update_idletasks()
        app._canvas_image_id = app.canvas.create_image(60, 100)
        app._scaled_size = (100, 100)

        app._reposition_current_image()

        coords = app.canvas.coords(app._canvas_image_id)
        assert coords[1] == app.canvas.winfo_height() // 2
    finally:
        app.cleanup()


def test_reposition_current_image_center_branch_sets_center_anchor(tk_root: tk.Tk) -> None:
    """_reposition_current_image should use centered placement for short images."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app._canvas_image_id = 1
        app._scaled_size = (100, 80)
        with (
            patch.object(app.canvas, "winfo_width", return_value=120),
            patch.object(app.canvas, "winfo_height", return_value=200),
            patch.object(app.canvas, "itemconfigure") as itemconfigure,
            patch.object(app.canvas, "coords") as coords,
        ):
            app._reposition_current_image()
        itemconfigure.assert_called_once_with(1, anchor="center")
        coords.assert_called_once_with(1, 60, 100)
    finally:
        app.cleanup()


def test_scroll_by_returns_when_image_fits_canvas(tk_root: tk.Tk) -> None:
    """_scroll_by should return early when no vertical scrolling is needed."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app._scaled_size = (100, 50)
        app._scroll_offset = 0
        with patch.object(app.canvas, "winfo_height", return_value=200):
            app._scroll_by(120)
        assert app._scroll_offset == 0
    finally:
        app.cleanup()


def test_update_from_cache_returns_when_no_source(tk_root: tk.Tk) -> None:
    """_update_from_cache should no-op cleanly when source is unavailable."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app.source = None
        app._update_from_cache(0, Image.new("RGB", (10, 10), color="white"))
    finally:
        app.cleanup()


def test_update_from_cache_returns_on_index_mismatch(tk_root: tk.Tk) -> None:
    """_update_from_cache should skip updates for non-current page indices."""
    app = _viewer_with_mock_source(tk_root)
    try:
        app._current_index = 0
        with patch.object(app, "_display_cached_image") as display:
            app._update_from_cache(1, Image.new("RGB", (10, 10), color="white"))
        display.assert_not_called()
    finally:
        app.cleanup()
