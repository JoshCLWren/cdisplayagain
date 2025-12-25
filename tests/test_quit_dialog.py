"""Test that quit command works even when load dialog is open."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def test_dialog_has_quit_bindings():
    """Verify that custom open dialog has quit key bindings."""
    root = tk.Tk()

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
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
            patch("tkinter.filedialog.askopenfilename"),
            patch("tkinter.filedialog.askopenfilenames"),
            patch("PIL.Image.open") as mock_img_open,
        ):
            mock_img = Mock()
            mock_img.mode = "RGB"
            mock_img.size = (100, 100)
            mock_img.resize.return_value = mock_img
            mock_img.convert.return_value = mock_img
            mock_img.save = lambda buf, **kwargs: buf.write(valid_image_bytes)
            mock_img_open.return_value = mock_img

            root.overrideredirect(True)
            root.geometry("1x1+0+0")

            app = ComicViewer(root, Path("dummy.cbz"))
            app.focus_set()
            root.update()

            assert not app._dialog_active

            mock_dialog = MagicMock()
            mock_dialog.title = Mock()
            mock_dialog.bind = Mock(return_value="callback")
            mock_dialog.destroy = Mock()

            def mock_wait_window(window):
                pass

            with patch("tkinter.Toplevel", return_value=mock_dialog):
                with patch.object(root, "wait_window", mock_wait_window):
                    app._open_dialog()

                    bind_calls = [call_args[0][0] for call_args in mock_dialog.bind.call_args_list]
                    assert "<Escape>" in bind_calls, "Dialog should have Escape binding"
                    assert "q" in bind_calls, "Dialog should have 'q' key binding"
                    assert "Q" in bind_calls, "Dialog should have 'Q' key binding"
                    assert "x" in bind_calls, "Dialog should have 'x' key binding"

    root.destroy()
