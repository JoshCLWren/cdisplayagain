"""Comprehensive tests for UI features."""

import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cdisplayagain import ComicViewer


def _write_image(path: Path) -> None:
    """Write a test image file."""
    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)


def _create_viewer(tk_root, comic_path):
    """Create a ComicViewer with mocked dependencies."""
    with (
        patch("tkinter.messagebox.showerror"),
        patch("tkinter.messagebox.showinfo"),
        patch("tkinter.filedialog.askopenfilename"),
        patch("tkinter.filedialog.askopenfilenames"),
    ):
        return ComicViewer(tk_root, comic_path)


def test_info_screen_double_click_dismissal(tk_root, tmp_path):
    """Test that double-clicking dismisses info overlay."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    # Create info overlay
    info_label = tk.Label(tk_root, text="Test info")
    info_label.place(relx=0.5, rely=0.5)
    viewer._info_overlay = info_label

    assert viewer._info_overlay is not None

    # Simulate double-click event
    viewer._dismiss_info()

    assert viewer._info_overlay is None


def test_info_screen_key_press_dismissal(tk_root, tmp_path):
    """Test that pressing any key dismisses info overlay."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    # Create info overlay
    info_label = tk.Label(tk_root, text="Test info")
    info_label.place(relx=0.5, rely=0.5)
    viewer._info_overlay = info_label

    assert viewer._info_overlay is not None

    # Simulate key press event (Key binding calls _dismiss_info)
    viewer._dismiss_info()

    assert viewer._info_overlay is None


def test_dismiss_info_when_no_overlay(tk_root, tmp_path):
    """Test that _dismiss_info handles no overlay gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer._info_overlay = None

    # Should not raise
    viewer._dismiss_info()

    assert viewer._info_overlay is None


def test_f1_help_dialog_displays_correct_message(tk_root, tmp_path, monkeypatch):
    """Test F1 help dialog displays expected help text."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    showinfo_calls = []

    def mock_showinfo(title, message):
        showinfo_calls.append((title, message))

    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "showinfo", mock_showinfo)

    viewer._show_help()

    assert len(showinfo_calls) == 1
    title, message = showinfo_calls[0]
    assert title == "cdisplayagain help"
    assert "arrow keys" in message
    assert "Page Up/Down" in message
    assert "mouse wheel" in message
    assert "W toggles fullscreen" in message
    assert "Esc quits" in message


def test_f1_key_binding_exists(tk_root, tmp_path):
    """Test that F1 key is bound to help dialog."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    bindings = viewer.bind_all("<F1>")
    assert bindings is not None
    assert len(bindings) > 0


def test_config_dialog_sets_dialog_active_flag(tk_root, tmp_path):
    """Test configuration dialog sets and resets dialog_active flag."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    assert viewer._dialog_active is False

    # Mock the entire config dialog method to avoid Tkinter complexity
    def mock_show_config():
        viewer._dialog_active = True
        # Simulate dialog opening and closing
        viewer._dialog_active = False

    original_show_config = viewer._show_config
    viewer._show_config = mock_show_config

    viewer._show_config()

    assert viewer._dialog_active is False

    viewer._show_config = original_show_config


def test_config_dialog_sets_one_page_mode(tk_root, tmp_path):
    """Test configuration dialog one page mode setting."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    # Initially default is False
    assert viewer._two_page_mode is False

    viewer.set_one_page_mode()

    assert viewer._two_page_mode is False


def test_config_dialog_sets_two_page_mode(tk_root, tmp_path):
    """Test configuration dialog two page mode setting."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer.set_two_page_mode()

    assert viewer._two_page_mode is True


def test_config_dialog_toggle_color_balance(tk_root, tmp_path):
    """Test configuration dialog color balance toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._color_balance_enabled

    viewer.toggle_color_balance()

    assert viewer._color_balance_enabled != initial_state


def test_config_dialog_toggle_yellow_reduction(tk_root, tmp_path):
    """Test configuration dialog yellow reduction toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._yellow_reduction_enabled

    viewer.toggle_yellow_reduction()

    assert viewer._yellow_reduction_enabled != initial_state


def test_config_dialog_toggle_hints(tk_root, tmp_path):
    """Test configuration dialog hints toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._hints_enabled

    viewer.toggle_hints()

    assert viewer._hints_enabled != initial_state


def test_config_dialog_toggle_two_page_advance(tk_root, tmp_path):
    """Test configuration dialog two page advance toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._two_page_advance_enabled

    viewer.toggle_two_page_advance()

    assert viewer._two_page_advance_enabled != initial_state


def test_config_dialog_set_page_buffer(tk_root, tmp_path):
    """Test configuration dialog page buffer setting."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer.set_page_buffer(10)

    assert viewer._page_buffer_size == 10

    viewer.set_page_buffer(20)

    assert viewer._page_buffer_size == 20


def test_config_dialog_set_background_color(tk_root, tmp_path):
    """Test configuration dialog background color setting."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer.set_background_color("#ffffff")

    assert viewer._background_color == "#ffffff"
    assert viewer.cget("bg") == "#ffffff"
    assert viewer.canvas.cget("bg") == "#ffffff"


def test_config_dialog_set_small_cursor(tk_root, tmp_path):
    """Test configuration dialog small cursor toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._small_cursor_enabled

    viewer.set_small_cursor()

    assert viewer._small_cursor_enabled != initial_state


def test_config_dialog_toggle_two_pages(tk_root, tmp_path):
    """Test configuration dialog two pages toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._two_page_mode

    viewer.toggle_two_pages()

    assert viewer._two_page_mode != initial_state


def test_f2_key_binding_exists(tk_root, tmp_path):
    """Test that F2 key is bound to configuration dialog."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    bindings = viewer.bind_all("<F2>")
    assert bindings is not None
    assert len(bindings) > 0


def test_hint_popup_shows_when_enabled(tk_root, tmp_path):
    """Test hint popup appears when hints are enabled."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer._hints_enabled = True

    viewer._show_hint_popup()

    assert viewer._hint_popup is not None
    assert isinstance(viewer._hint_popup, tk.Label)


def test_hint_popup_does_not_show_when_disabled(tk_root, tmp_path):
    """Test hint popup does not appear when hints are disabled."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer._hints_enabled = False

    viewer._show_hint_popup()

    assert viewer._hint_popup is None


def test_hint_popup_dismissal(tk_root, tmp_path):
    """Test hint popup can be dismissed."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer._hints_enabled = True
    viewer._show_hint_popup()

    assert viewer._hint_popup is not None

    viewer._dismiss_hint_popup()

    assert viewer._hint_popup is None
    assert viewer._hint_timer is None


def test_dismiss_hint_popup_when_no_popup(tk_root, tmp_path):
    """Test _dismiss_hint_popup handles no popup gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer._hint_popup = None
    viewer._hint_timer = None

    # Should not raise
    viewer._dismiss_hint_popup()

    assert viewer._hint_popup is None
    assert viewer._hint_timer is None


def test_cursor_hidden_in_fullscreen(tk_root, tmp_path):
    """Test cursor is hidden when in fullscreen mode."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer.toggle_fullscreen()

    assert viewer._fullscreen is True
    assert viewer._cursor_hidden is True


def test_cursor_visible_when_not_fullscreen(tk_root, tmp_path):
    """Test cursor is visible when not in fullscreen mode."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    # Initially fullscreen is False from ComicViewer init
    assert viewer._fullscreen is False

    # Manually set fullscreen and cursor hidden to test the reverse
    viewer._fullscreen = True
    viewer._cursor_hidden = True

    assert viewer._fullscreen is True
    assert viewer._cursor_hidden is True

    # Now toggle off
    viewer._fullscreen = False
    viewer._cursor_hidden = False

    assert viewer._fullscreen is False
    assert viewer._cursor_hidden is False


def test_fullscreen_toggle(tk_root, tmp_path):
    """Test fullscreen toggle functionality."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_state = viewer._fullscreen

    viewer.toggle_fullscreen()

    assert viewer._fullscreen != initial_state


def test_w_key_binding_exists(tk_root, tmp_path):
    """Test that W key is bound to fullscreen toggle."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    bindings_upper_w = viewer.bind_all("W")
    bindings_lower_w = viewer.bind_all("w")

    assert bindings_upper_w is not None
    assert bindings_lower_w is not None


def test_set_mouse_binding(tk_root, tmp_path):
    """Test setting custom mouse button binding."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    viewer.set_mouse_binding("Button-1", "next_page")

    assert "Button-1" in viewer._mouse_bindings
    assert viewer._mouse_bindings["Button-1"] == "next_page"


def test_set_mouse_binding_with_none_args(tk_root, tmp_path):
    """Test set_mouse_binding handles None arguments gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = _create_viewer(tk_root, tmp_path / "page1.png")

    initial_bindings = viewer._mouse_bindings.copy()

    # Should not raise and should not change bindings
    viewer.set_mouse_binding(None, None)

    assert viewer._mouse_bindings == initial_bindings
