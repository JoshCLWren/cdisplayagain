"""Test that quit command works even when load dialog is open."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def test_dialog_has_quit_bindings():
    """Verify that the custom open dialog has quit key bindings."""
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

            quit_called = [False]
            dialog_widget = [None]

            def mock_quit():
                quit_called[0] = True

            original_open = tk.Toplevel.__init__

            def track_toplevel_init(self, master, **kwargs):
                original_open(self, master, **kwargs)
                dialog_widget[0] = self

            with patch.object(tk.Toplevel, "__init__", track_toplevel_init):
                with patch.object(app, "_quit", mock_quit):

                    def mock_wait_window(window):
                        window.event_generate("q")
                        window.update()

                    with patch.object(root, "wait_window", mock_wait_window):
                        app._open_dialog()

                    assert dialog_widget[0] is not None, "Dialog should have been created"
                    bindings = dialog_widget[0].bind("q")
                    assert len(bindings) > 0, "Dialog should have 'q' key binding"

                    bindings_esc = dialog_widget[0].bind("<Escape>")
                    assert len(bindings_esc) > 0, "Dialog should have Escape binding"

                    assert quit_called[0], "Quit should have been called"

    root.destroy()
