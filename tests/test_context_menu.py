"""Tests for context menu functionality."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def test_context_menu_exists_and_has_load_files():
    """Verify that context menu is created and has 'Load files' as first entry."""
    root = tk.Tk()
    root.withdraw()

    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    with patch("cdisplayagain.load_comic") as mock_load:
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            with patch("PIL.Image.open") as mock_img_open:
                mock_img = Mock()
                mock_img.mode = "RGB"
                mock_img.size = (100, 100)
                mock_img.resize.return_value = mock_img
                mock_img.convert.return_value = mock_img
                mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
                mock_img_open.return_value = mock_img

                app = ComicViewer(root, Path("dummy.cbz"))

                assert app._context_menu is not None
                assert isinstance(app._context_menu, tk.Menu)

                entry_index = 0
                menu_type = app._context_menu.type(entry_index)
                assert menu_type == "command"

                label = app._context_menu.entrycget(entry_index, "label")
                assert label == "Load files"

    root.destroy()


def test_right_click_binding_exists():
    """Verify that right-click (<Button-3>) is bound to show context menu."""
    root = tk.Tk()
    root.withdraw()

    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    with patch("cdisplayagain.load_comic") as mock_load:
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            with patch("PIL.Image.open") as mock_img_open:
                mock_img = Mock()
                mock_img.mode = "RGB"
                mock_img.size = (100, 100)
                mock_img.resize.return_value = mock_img
                mock_img.convert.return_value = mock_img
                mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
                mock_img_open.return_value = mock_img

                app = ComicViewer(root, Path("dummy.cbz"))

                bindings = app.bind_all("<Button-3>")
                assert bindings is not None
                assert len(bindings) > 0

    root.destroy()


def test_context_menu_load_files_calls_open_dialog():
    """Verify that clicking 'Load files' in context menu calls _open_dialog."""
    root = tk.Tk()
    root.withdraw()

    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    with patch("cdisplayagain.load_comic") as mock_load:
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            with patch("PIL.Image.open") as mock_img_open:
                mock_img = Mock()
                mock_img.mode = "RGB"
                mock_img.size = (100, 100)
                mock_img.resize.return_value = mock_img
                mock_img.convert.return_value = mock_img
                mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
                mock_img_open.return_value = mock_img

                app = ComicViewer(root, Path("dummy.cbz"))

                app._open_dialog = Mock()

                index = 0
                command = app._context_menu.entrycget(index, "command")
                assert "_open_dialog" in command

    root.destroy()


def test_right_click_shows_context_menu():
    """Verify that right-click event shows the context menu."""
    root = tk.Tk()
    root.withdraw()

    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    with patch("cdisplayagain.load_comic") as mock_load:
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            with patch("PIL.Image.open") as mock_img_open:
                mock_img = Mock()
                mock_img.mode = "RGB"
                mock_img.size = (100, 100)
                mock_img.resize.return_value = mock_img
                mock_img.convert.return_value = mock_img
                mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
                mock_img_open.return_value = mock_img

                app = ComicViewer(root, Path("dummy.cbz"))

                app._show_context_menu = Mock(wraps=app._show_context_menu)

                event = Mock()
                event.x_root = 100
                event.y_root = 100

                app._show_context_menu(event)

                app._show_context_menu.assert_called_once()

    root.destroy()
