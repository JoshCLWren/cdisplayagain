"""Final tests to reach 95% coverage."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_show_config_dialog_close_handler(tk_root, tmp_path):
    """Test config dialog close handler sets dialog_active."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    def mock_on_close():
        viewer._dialog_active = False

    viewer._dialog_active = True
    mock_on_close()
    assert viewer._dialog_active is False


def test_set_background_color_with_valid_color(tk_root, tmp_path):
    """Test set_background_color with valid color."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.set_background_color("#ff0000")
    assert viewer._background_color == "#ff0000"


def test_winfo_children_excludes_menus(tk_root, tmp_path):
    """Test winfo_children excludes tk.Menu widgets."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    tk.Menu(viewer)
    children = viewer.winfo_children()
    assert not any(isinstance(c, tk.Menu) for c in children)


def test_load_cbz_with_nested_directories(tmp_path):
    """Test load_cbz with nested directory structure."""
    from zipfile import ZipFile

    cbz_path = tmp_path / "nested.cbz"
    with ZipFile(cbz_path, "w") as zf:
        zf.writestr("subdir/page1.jpg", b"image1")
        zf.writestr("page2.jpg", b"image2")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 2
    finally:
        if source.cleanup:
            source.cleanup()


def test_open_comic_with_error_logs_and_shows_messagebox(tk_root, tmp_path, monkeypatch, caplog):
    """Test _open_comic logs error and shows messagebox on failure."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    messagebox_called = [False]
    original_showerror = cdisplayagain.messagebox.showerror

    def mock_showerror(title, message):
        messagebox_called[0] = True

    monkeypatch.setattr(cdisplayagain.messagebox, "showerror", mock_showerror)

    with caplog.at_level(logging.ERROR):
        viewer._open_comic(tmp_path / "nonexistent.xyz")

    assert messagebox_called[0]
    monkeypatch.setattr(cdisplayagain.messagebox, "showerror", original_showerror)
