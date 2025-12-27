"""Regression test for BUG-001: crash when quitting while load dialog is open."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def test_quit_reentrancy_guard():
    """Verify that _quit cannot be called multiple times due to re-entrancy guard."""
    root = tk.Tk()
    root.withdraw()

    # Create a valid image for testing
    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    # Mock load_comic to avoid needing a real file
    with patch("cdisplayagain.load_comic") as mock_load:
        mock_source = Mock()
        mock_source.pages = ["page1.jpg"]
        mock_source.cleanup = None
        mock_source.get_bytes.return_value = valid_image_bytes
        mock_load.return_value = mock_source

        with (
            patch("PIL.Image.open") as mock_img_open,
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
        ):
            mock_img = Mock()
            mock_img.mode = "RGB"
            mock_img.size = (100, 100)
            mock_img.resize.return_value = mock_img
            mock_img.convert.return_value = mock_img
            mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
            mock_img_open.return_value = mock_img

            app = ComicViewer(root, Path("dummy.cbz"))
            root.update()

            # Mock master.destroy to track when it's called
            destroy_mock = Mock()
            original_master_destroy = app.master.destroy
            app.master.destroy = destroy_mock

            # Simulate the bug scenario: dialog is active and quit is called
            app._dialog_active = True
            app._quit()  # First call, should set _pending_quit = True but not _quitting

            # Verify state after first quit
            assert app._quitting is False, "_quitting should not be set while dialog is active"
            assert app._pending_quit is True, "_pending_quit should be set"
            destroy_mock.assert_not_called()

            # Simulate dialog closing and _open_dialog's finally block calling _quit
            app._dialog_active = False
            app._quit()  # This should complete the quit

            # Verify quit completed
            assert app._quitting is True, "_quitting should be set after quit completes"
            destroy_mock.assert_called_once()

            # Reset for another test
            app._quitting = False
            app._pending_quit = False
            destroy_mock.reset_mock()

            # Test normal quit path (no dialog)
            app._quit()
            destroy_mock.assert_called_once()
            assert app._quitting is True

            # Try to quit again - should be ignored
            app._quit()
            destroy_mock.assert_called_once()

            app.master.destroy = original_master_destroy

            app.master.destroy = original_master_destroy

    root.destroy()
