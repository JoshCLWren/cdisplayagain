"""Test main function entry points and utility functions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import cdisplayagain


def _write_image(path: Path) -> None:
    """Write a test image file."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)


def test_require_unar_with_unavailable_module(monkeypatch):
    """Test require_unar raises SystemExit when module is unavailable."""
    # Mock importlib.util.find_spec to return None (module not found)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)

    # Test on Linux
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(SystemExit, match="CBR support requires 'unrar2-cffi'"):
        cdisplayagain.require_unar()

    # Test on macOS
    monkeypatch.setattr("sys.platform", "darwin")
    with pytest.raises(SystemExit, match="CBR support requires 'unrar2-cffi'"):
        cdisplayagain.require_unar()

    # Test on other platforms
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.raises(SystemExit, match="CBR support requires 'unrar2-cffi'"):
        cdisplayagain.require_unar()


def test_require_unar_with_available_module(monkeypatch):
    """Test require_unar succeeds when module is available."""
    # Mock importlib.util.find_spec to return a fake spec
    fake_spec = MagicMock()
    monkeypatch.setattr("importlib.util.find_spec", lambda name: fake_spec)

    # Should not raise any exception
    cdisplayagain.require_unar()


def test_main_function_with_file_argument(monkeypatch, tmp_path):
    """Test main function with command line file argument."""
    _write_image(tmp_path / "test.png")

    # Mock ComicViewer to track its instantiation
    mock_viewer = MagicMock()

    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.Canvas"),
        patch("tkinter.Scrollbar"),
        patch("tkinter.Frame"),
        patch.object(cdisplayagain, "ComicViewer", mock_viewer),
    ):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Mock sys.argv to include file argument
        test_args = ["cdisplayagain.py", str(tmp_path / "test.png")]
        with patch("sys.argv", test_args):
            cdisplayagain.main()

        # Verify ComicViewer was called with correct path
        mock_viewer.assert_called_once()
        args, kwargs = mock_viewer.call_args
        assert args[1] == tmp_path / "test.png"

        # Verify Tk setup was called
        mock_root.withdraw.assert_called_once()
        mock_root.attributes.assert_called_with("-fullscreen", True)
        mock_root.deiconify.assert_called_once()


def test_main_function_with_no_file_argument_cancelled(monkeypatch, tmp_path):
    """Test main function when user cancels file dialog."""
    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.filedialog.askopenfilename", return_value=""),
        patch.object(cdisplayagain, "ComicViewer"),
    ):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Mock sys.argv with no file argument
        test_args = ["cdisplayagain.py"]
        with patch("sys.argv", test_args):
            cdisplayagain.main()

        # Verify cleanup was called
        mock_root.destroy.assert_called_once()


def test_main_function_with_nonexistent_file(monkeypatch, tmp_path):
    """Test main function with nonexistent file path."""
    with (
        patch("tkinter.Tk") as mock_tk,
        patch("sys.exit") as mock_exit,
        patch("builtins.print") as mock_print,
        patch.object(cdisplayagain, "ComicViewer"),
    ):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Test with nonexistent file
        nonexistent_path = tmp_path / "nonexistent.png"
        test_args = ["cdisplayagain.py", str(nonexistent_path)]
        with patch("sys.argv", test_args):
            cdisplayagain.main()

        # Verify error was printed and sys.exit called
        mock_print.assert_called_with(
            f"File not found: {nonexistent_path}",
            file=mock_print.call_args.kwargs["file"] if mock_print.call_args.kwargs else sys.stderr,
        )
        mock_exit.assert_called_with(1)
        mock_root.destroy.assert_called_once()


def test_main_function_with_file_dialog_selection(monkeypatch, tmp_path):
    """Test main function when user selects file via dialog."""
    _write_image(tmp_path / "selected.png")

    # Mock ComicViewer to track its instantiation
    mock_viewer = MagicMock()

    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.Canvas"),
        patch("tkinter.Scrollbar"),
        patch("tkinter.Frame"),
        patch("tkinter.filedialog.askopenfilename", return_value=str(tmp_path / "selected.png")),
        patch.object(cdisplayagain, "ComicViewer", mock_viewer),
    ):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Mock sys.argv with no file argument (user will use dialog)
        test_args = ["cdisplayagain.py"]
        with patch("sys.argv", test_args):
            cdisplayagain.main()

        # Verify ComicViewer was called with selected file
        mock_viewer.assert_called_once()
        args, kwargs = mock_viewer.call_args
        assert args[1] == tmp_path / "selected.png"
