"""Tests for the macOS openDocument Apple Event path used by Finder launches."""

import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import cdisplayagain


@pytest.fixture(autouse=True)
def clear_pending_documents():
    """Keep the module-level openDocument queue from leaking between tests."""
    cdisplayagain._PENDING_OPEN_DOCUMENTS.clear()
    yield
    cdisplayagain._PENDING_OPEN_DOCUMENTS.clear()


def test_comic_path_from_argument_plain_path():
    """A plain filesystem path passes through unchanged."""
    assert cdisplayagain.comic_path_from_argument("/comics/issue.cbz") == Path("/comics/issue.cbz")


def test_comic_path_from_argument_expands_user():
    """A tilde path expands to the user's home directory."""
    result = cdisplayagain.comic_path_from_argument("~/issue.cbz")
    assert result == Path.home() / "issue.cbz"
    assert "~" not in str(result)


def test_comic_path_from_argument_file_url():
    """A file:// URL becomes a real path rather than a single stray character."""
    assert cdisplayagain.comic_path_from_argument("file:///comics/issue.cbz") == Path(
        "/comics/issue.cbz"
    )


def test_comic_path_from_argument_file_url_with_escaped_space():
    """Percent-encoded characters in a file:// URL are decoded."""
    result = cdisplayagain.comic_path_from_argument("file:///comics/my%20issue.cbz")
    assert result == Path("/comics/my issue.cbz")


def test_register_open_document_handler_skips_non_darwin(monkeypatch):
    """Non-macOS platforms report no handler so callers fall back to argv."""
    monkeypatch.setattr(sys, "platform", "linux")
    root = MagicMock()

    assert cdisplayagain.register_open_document_handler(root) is False
    root.createcommand.assert_not_called()


def test_register_open_document_handler_registers_on_darwin(monkeypatch):
    """Register the Tk command Finder delivers documents through on macOS."""
    monkeypatch.setattr(sys, "platform", "darwin")
    root = MagicMock()

    assert cdisplayagain.register_open_document_handler(root) is True
    command_name, callback = root.createcommand.call_args[0]
    assert command_name == "::tk::mac::OpenDocument"
    assert callback is cdisplayagain._record_open_document


def test_register_open_document_handler_accepts_custom_callback(monkeypatch):
    """A caller-supplied callback replaces the default queueing handler."""
    monkeypatch.setattr(sys, "platform", "darwin")
    root = MagicMock()
    callback = MagicMock()

    cdisplayagain.register_open_document_handler(root, callback)

    assert root.createcommand.call_args[0][1] is callback


def test_register_open_document_handler_survives_tcl_error(monkeypatch):
    """A Tk build without the mac command degrades to the argv path."""
    monkeypatch.setattr(sys, "platform", "darwin")
    root = MagicMock()
    root.createcommand.side_effect = tk.TclError("no such command")

    assert cdisplayagain.register_open_document_handler(root) is False


def test_await_open_document_returns_queued_path():
    """A document delivered while pumping the event loop is returned."""
    root = MagicMock()
    root.update.side_effect = lambda: cdisplayagain._record_open_document("/comics/issue.cbz")

    assert cdisplayagain.await_open_document(root, timeout_ms=500) == "/comics/issue.cbz"


def test_await_open_document_returns_none_on_timeout():
    """No Apple Event within the window means fall through to the file dialog."""
    root = MagicMock()

    assert cdisplayagain.await_open_document(root, timeout_ms=1) is None


def test_await_open_document_consumes_only_first_path():
    """Only the first queued document is consumed by the launch-time wait."""
    cdisplayagain._record_open_document("/comics/one.cbz", "/comics/two.cbz")
    root = MagicMock()

    assert cdisplayagain.await_open_document(root, timeout_ms=1) == "/comics/one.cbz"
    assert cdisplayagain._PENDING_OPEN_DOCUMENTS == ["/comics/two.cbz"]


def test_open_documents_in_viewer_loads_path(tmp_path):
    """A document sent to a running viewer is opened and focused."""
    comic = tmp_path / "issue.cbz"
    comic.write_bytes(b"")
    app = MagicMock()

    cdisplayagain._open_documents_in_viewer(app, [str(comic)])

    app._open_comic.assert_called_once_with(comic)
    app._request_focus.assert_called_once()


def test_open_documents_in_viewer_ignores_empty_event():
    """An openDocument event with no paths is a no-op."""
    app = MagicMock()

    cdisplayagain._open_documents_in_viewer(app, [])

    app._open_comic.assert_not_called()


def test_open_documents_in_viewer_ignores_missing_file(tmp_path):
    """A path that no longer exists does not reach the loader."""
    app = MagicMock()

    cdisplayagain._open_documents_in_viewer(app, [str(tmp_path / "gone.cbz")])

    app._open_comic.assert_not_called()


def test_main_prefers_open_document_over_file_dialog(monkeypatch, tmp_path):
    """On macOS with no argv path, a Finder document wins over the picker."""
    from PIL import Image

    comic = tmp_path / "issue.png"
    Image.new("RGB", (10, 10), color="red").save(comic)
    monkeypatch.setattr(sys, "platform", "darwin")

    with (
        patch("tkinter.Tk") as mock_tk,
        patch.object(cdisplayagain, "ComicViewer") as mock_viewer,
        patch.object(cdisplayagain, "await_open_document", return_value=str(comic)),
        patch("tkinter.filedialog.askopenfilename") as mock_dialog,
        patch("sys.argv", ["cdisplayagain.py"]),
    ):
        mock_tk.return_value = MagicMock()
        cdisplayagain.main()

    mock_dialog.assert_not_called()
    assert mock_viewer.call_args[0][1] == comic


def test_main_falls_back_to_dialog_without_open_document(monkeypatch, tmp_path):
    """When no Apple Event arrives, macOS still shows the Open Comic dialog."""
    from PIL import Image

    comic = tmp_path / "issue.png"
    Image.new("RGB", (10, 10), color="red").save(comic)
    monkeypatch.setattr(sys, "platform", "darwin")

    with (
        patch("tkinter.Tk") as mock_tk,
        patch.object(cdisplayagain, "ComicViewer") as mock_viewer,
        patch.object(cdisplayagain, "await_open_document", return_value=None),
        patch("tkinter.filedialog.askopenfilename", return_value=str(comic)) as mock_dialog,
        patch("sys.argv", ["cdisplayagain.py"]),
    ):
        mock_tk.return_value = MagicMock()
        cdisplayagain.main()

    mock_dialog.assert_called_once()
    assert mock_viewer.call_args[0][1] == comic
