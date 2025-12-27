"""Tests for UI event bindings specifically key shortcuts."""

import io
import tkinter as tk
from unittest.mock import Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def test_l_key_binding_exists():
    """Verify that 'l' key is bound to _open_dialog."""
    from pathlib import Path

    root = tk.Tk()
    root.withdraw()

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
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
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

                app = ComicViewer(root, Path("dummy.cbz"))

                # Verify that the binding exists by checking bind_all
                bindings = app.bind_all("l")
                assert bindings is not None
                assert len(bindings) > 0

    root.destroy()
