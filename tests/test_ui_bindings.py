"""Tests for UI event bindings specifically key shortcuts."""

import io
import tkinter as tk
from unittest.mock import Mock, patch
from cdisplayagain import ComicViewer
from pathlib import Path
from PIL import Image


def test_l_key_triggers_open_dialog():
    """Verify that pressing 'l' calls _open_dialog regardless of focus."""
    root = tk.Tk()
    # root.withdraw()  <-- Removing this so it is visible

    # Create a valid image for testing
    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    # Mock load_comic so we don't need a real file
    with patch("cdisplayagain.load_comic") as mock_load:
        # Return a dummy source with one page
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("tkinter.filedialog.askopenfilename", return_value="dummy.cbz"),
            patch("tkinter.filedialog.askopenfilenames", return_value=["dummy.cbz"]),
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            with patch("PIL.Image.open") as mock_img_open:
                # Mock the Image object
                mock_img = Mock()
                mock_img.mode = "RGB"
                mock_img.size = (100, 100)
                mock_img.resize.return_value = mock_img
                mock_img.convert.return_value = mock_img
                mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
                mock_img_open.return_value = mock_img

                # Make window tiny and frameless to reduce visual noise
                root.overrideredirect(True)
                root.geometry("1x1+0+0")

                app = ComicViewer(root, Path("dummy.cbz"))

                # Ensure app is focused
                app.focus_set()
                root.update()

                # Mock the _open_dialog method to verify it gets called
                # We patch it on the instance
                app._open_dialog = Mock(wraps=app._open_dialog)

                # Simulate pressing 'l'. explicit keysym is safer for tests
                # Generate on app widget
                app.event_generate("l")  # Try simple char first as bind_all "l" matches keypress
                root.update()

                app._open_dialog.assert_called_once()

    root.destroy()
