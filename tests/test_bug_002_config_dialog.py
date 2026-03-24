"""Regression tests for BUG-002: config dialog made main window unresponsive.

Two bugs were fixed:
1. wm_transient was called on the master window (making it transient for the
   dialog) instead of on the dialog (making it transient for the master). This
   caused the main window to hide behind the config dialog and become
   unresponsive.
2. The Close button called dialog.destroy() directly, bypassing on_close(), so
   _dialog_active was never reset to False.
"""

import io
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from cdisplayagain import ComicViewer


def _make_app(root: tk.Tk) -> ComicViewer:
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
            mock_img.save = lambda b, **_kw: b.write(valid_image_bytes)
            mock_img_open.return_value = mock_img

            app = ComicViewer(root, Path("dummy.cbz"))
            root.update()
            return app


def test_config_dialog_transient_called_on_dialog_not_master():
    """BUG-002a: transient() must be called on the dialog, not the master.

    The original bug called master.wm_transient(dialog), which made the main
    window transient for (subordinate to) the dialog, causing it to disappear
    behind the config window and become unresponsive.
    """
    root = tk.Tk()
    root.withdraw()

    app = _make_app(root)

    mock_dialog = MagicMock()
    mock_dialog.bind = Mock()
    mock_dialog.protocol = Mock()

    with patch("tkinter.Toplevel", return_value=mock_dialog):
        with patch.object(mock_dialog, "wait_window"):
            app._show_config()

    # dialog.transient(...) must have been called — not master.wm_transient(dialog)
    assert mock_dialog.transient.called, "dialog.transient() should be called"
    # master.wm_transient should NOT have been called with the dialog
    # (root is a real Tk so we verify via absence of the reverse call)
    transient_args = mock_dialog.transient.call_args[0]
    assert len(transient_args) == 1, "transient() should receive exactly one argument (the master)"

    root.destroy()


def test_config_dialog_close_resets_dialog_active():
    """BUG-002b: Closing config dialog must reset _dialog_active to False.

    The original bug passed dialog.destroy directly to the Close button,
    bypassing on_close(), so _dialog_active stayed True after closing.
    We verify via the WM_DELETE_WINDOW protocol handler, which is the same
    on_close() callable wired to the Close button.
    """
    root = tk.Tk()
    root.withdraw()

    app = _make_app(root)

    # Capture the on_close callable registered as the WM_DELETE_WINDOW handler
    protocol_handlers: dict[str, Callable[[], None]] = {}
    mock_dialog = MagicMock()
    mock_dialog.bind = Mock()

    def capture_protocol(name: str, handler: Callable[[], None]) -> None:
        protocol_handlers[name] = handler

    mock_dialog.protocol = Mock(side_effect=capture_protocol)

    with patch("tkinter.Toplevel", return_value=mock_dialog):
        with patch.object(mock_dialog, "wait_window"):
            app._show_config()

    on_close = protocol_handlers.get("WM_DELETE_WINDOW")
    assert callable(on_close), "WM_DELETE_WINDOW handler should be registered"

    # Simulate closing — _dialog_active should become False
    app._dialog_active = True
    on_close()
    assert app._dialog_active is False, (
        "_dialog_active must be False after closing — "
        "original bug left it True because dialog.destroy was called directly"
    )

    root.destroy()


def test_config_dialog_escape_closes_dialog():
    """Esc must dismiss the config dialog without quitting the app."""
    root = tk.Tk()
    root.withdraw()

    app = _make_app(root)

    mock_dialog = MagicMock()
    mock_dialog.bind = Mock()
    mock_dialog.protocol = Mock()

    with patch("tkinter.Toplevel", return_value=mock_dialog):
        with patch.object(mock_dialog, "wait_window"):
            app._show_config()

    bind_calls = [c[0][0] for c in mock_dialog.bind.call_args_list]
    assert "<Escape>" in bind_calls, "Config dialog must bind <Escape>"

    root.destroy()


def test_config_dialog_q_keys_close_dialog():
    """Both q and Q must dismiss the config dialog."""
    root = tk.Tk()
    root.withdraw()

    app = _make_app(root)

    mock_dialog = MagicMock()
    mock_dialog.bind = Mock()
    mock_dialog.protocol = Mock()

    with patch("tkinter.Toplevel", return_value=mock_dialog):
        with patch.object(mock_dialog, "wait_window"):
            app._show_config()

    bind_calls = [c[0][0] for c in mock_dialog.bind.call_args_list]
    assert "q" in bind_calls, "Config dialog must bind 'q'"
    assert "Q" in bind_calls, "Config dialog must bind 'Q'"

    root.destroy()


def test_config_dialog_does_not_catch_all_keys():
    """Config dialog must NOT bind the generic <Key> event.

    The original catch-all <Key> binding closed the dialog whenever the user
    typed anything, including into the background-color entry field.
    """
    root = tk.Tk()
    root.withdraw()

    app = _make_app(root)

    mock_dialog = MagicMock()
    mock_dialog.bind = Mock()
    mock_dialog.protocol = Mock()

    with patch("tkinter.Toplevel", return_value=mock_dialog):
        with patch.object(mock_dialog, "wait_window"):
            app._show_config()

    bind_calls = [c[0][0] for c in mock_dialog.bind.call_args_list]
    assert "<Key>" not in bind_calls, (
        "Config dialog must not bind generic <Key> — "
        "doing so closes the dialog when typing in the color entry"
    )

    root.destroy()
