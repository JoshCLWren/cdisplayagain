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


def test_require_pyvips_with_module_not_found(monkeypatch):
    """Test require_pyvips raises SystemExit when pyvips module is not found."""

    # Mock __import__ to raise ModuleNotFoundError for pyvips
    def mock_import(name, *args, **kwargs):
        if name == "pyvips":
            raise ModuleNotFoundError("No module named 'pyvips'")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.raises(SystemExit, match="pyvips is not installed"):
        cdisplayagain.require_pyvips()


def test_require_pyvips_with_oserror(monkeypatch):
    """Test require_pyvips raises SystemExit when libvips runtime is missing."""

    # Mock __import__ to raise OSError with libvips message
    def mock_import(name, *args, **kwargs):
        if name == "pyvips":
            raise OSError("dlopen: libvips.so.42: cannot open shared object file")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.raises(SystemExit, match="libvips could not be loaded"):
        cdisplayagain.require_pyvips()


def test_require_pyvips_success(monkeypatch):
    """Test require_pyvips succeeds when pyvips is available."""

    # Mock __import__ to return a fake module for pyvips
    def mock_import(name, *args, **kwargs):
        if name == "pyvips":
            return MagicMock()
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    # Should not raise any exception
    cdisplayagain.require_pyvips()


def test_require_pyvips_with_oserror_no_libvips(monkeypatch):
    """Test require_pyvips raises OSError when it's not a libvips issue."""

    # Mock __import__ to raise OSError without libvips message
    def mock_import(name, *args, **kwargs):
        if name == "pyvips":
            raise OSError("Some other OSError")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.raises(OSError, match="Some other OSError"):
        cdisplayagain.require_pyvips()
