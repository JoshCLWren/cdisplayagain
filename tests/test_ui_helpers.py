"""Test UI helper methods."""

import tkinter as tk
from pathlib import Path

import cdisplayagain


def _write_image(path: Path) -> None:
    """Write a test image file."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)


def test_minimize_functionality(tk_root, tmp_path, monkeypatch):
    """Test minimize functionality handles TclError gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    # Mock iconify to raise TclError
    def mock_iconify():
        raise tk.TclError("test error")

    monkeypatch.setattr(tk_root, "iconify", mock_iconify)

    # Should not raise exception
    viewer._minimize()  # line 986-991


def test_minimize_normal_operation(tk_root, tmp_path, monkeypatch):
    """Test minimize functionality works normally."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    # Mock iconify to track calls
    iconify_called = [False]

    def mock_iconify():
        iconify_called[0] = True

    monkeypatch.setattr(tk_root, "iconify", mock_iconify)

    viewer._minimize()
    assert iconify_called[0]


def test_dismiss_info_overlay(tk_root, tmp_path):
    """Test info overlay dismissal."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    # Test when no overlay exists
    viewer._info_overlay = None
    viewer._dismiss_info()  # Should not raise
    assert viewer._info_overlay is None

    # Test when overlay exists - create a fake overlay (normally would be a Label)
    viewer._info_overlay = tk.Label(tk_root, text="test")
    assert viewer._info_overlay is not None

    viewer._dismiss_info()  # lines 1000-1003
    assert viewer._info_overlay is None


def test_build_context_menu(tk_root, tmp_path):
    """Test context menu creation."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    menu = viewer._build_context_menu()  # lines 1005-1010
    assert isinstance(menu, tk.Menu)

    # Check that it has 3 menu items (Load files, Minimize, Quit)
    assert menu.index("end") == 2  # Index is 0-based, so 2 means 3 items

    # Test menu items exist
    assert menu.entrycget(0, "label") == "Load files"
    assert menu.entrycget(1, "label") == "Minimize"
    assert menu.entrycget(2, "label") == "Quit"


def test_show_help_dialog(tk_root, tmp_path, monkeypatch):
    """Test help dialog functionality."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    # Track messagebox.showinfo calls
    showinfo_called = []

    def mock_showinfo(title, message):
        showinfo_called.append((title, message))

    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "showinfo", mock_showinfo)

    viewer._show_help()

    assert len(showinfo_called) == 1
    title, message = showinfo_called[0]
    assert title == "cdisplayagain help"
    assert "arrow keys" in message
    assert "Page Up/Down" in message
    assert "W toggles fullscreen" in message
    assert "Esc quits" in message
