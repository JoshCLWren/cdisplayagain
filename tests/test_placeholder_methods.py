"""Test configuration parity methods."""

from pathlib import Path

import cdisplayagain


def _write_image(path: Path) -> None:
    """Write a test image file."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)


def test_set_one_page_mode(tk_root, tmp_path):
    """Test set_one_page_mode sets two_page_mode to False."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._two_page_mode = True
    viewer.set_one_page_mode()
    assert viewer._two_page_mode is False


def test_set_two_page_mode(tk_root, tmp_path):
    """Test set_two_page_mode sets two_page_mode to True."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._two_page_mode = False
    viewer.set_two_page_mode()
    assert viewer._two_page_mode is True


def test_toggle_color_balance(tk_root, tmp_path):
    """Test toggle_color_balance toggles the setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._color_balance_enabled
    viewer.toggle_color_balance()
    assert viewer._color_balance_enabled is not initial
    viewer.toggle_color_balance()
    assert viewer._color_balance_enabled is initial


def test_toggle_yellow_reduction(tk_root, tmp_path):
    """Test toggle_yellow_reduction toggles the setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._yellow_reduction_enabled
    viewer.toggle_yellow_reduction()
    assert viewer._yellow_reduction_enabled is not initial
    viewer.toggle_yellow_reduction()
    assert viewer._yellow_reduction_enabled is initial


def test_toggle_hints(tk_root, tmp_path):
    """Test toggle_hints toggles the setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._hints_enabled
    viewer.toggle_hints()
    assert viewer._hints_enabled is not initial
    viewer.toggle_hints()
    assert viewer._hints_enabled is initial


def test_toggle_two_pages(tk_root, tmp_path):
    """Test toggle_two_pages toggles the setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._two_page_mode
    viewer.toggle_two_pages()
    assert viewer._two_page_mode is not initial
    viewer.toggle_two_pages()
    assert viewer._two_page_mode is initial


def test_toggle_two_page_advance(tk_root, tmp_path):
    """Test toggle_two_page_advance toggles the setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._two_page_advance_enabled
    viewer.toggle_two_page_advance()
    assert viewer._two_page_advance_enabled is not initial
    viewer.toggle_two_page_advance()
    assert viewer._two_page_advance_enabled is initial


def test_set_page_buffer(tk_root, tmp_path):
    """Test set_page_buffer sets the buffer size."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer.set_page_buffer(10)
    assert viewer._page_buffer_size == 10
    viewer.set_page_buffer(20)
    assert viewer._page_buffer_size == 20
    viewer.set_page_buffer(0)
    assert viewer._page_buffer_size == 0
    viewer.set_page_buffer(None)
    assert viewer._page_buffer_size == 0


def test_set_background_color(tk_root, tmp_path):
    """Test set_background_color sets the background color."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer.set_background_color("#222222")
    assert viewer._background_color == "#222222"
    viewer.set_background_color("white")
    assert viewer._background_color == "white"
    viewer.set_background_color(None)
    assert viewer._background_color == "white"


def test_set_small_cursor(tk_root, tmp_path):
    """Test set_small_cursor toggles small cursor setting."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._small_cursor_enabled
    viewer.set_small_cursor()
    assert viewer._small_cursor_enabled is not initial
    viewer.set_small_cursor()
    assert viewer._small_cursor_enabled is initial


def test_set_mouse_binding(tk_root, tmp_path):
    """Test set_mouse_binding sets custom mouse binding."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer.set_mouse_binding("Button-1", "go_forward")
    assert viewer._mouse_bindings["Button-1"] == "go_forward"
    viewer.set_mouse_binding("Button-3", "go_back")
    assert viewer._mouse_bindings["Button-3"] == "go_back"


def test_show_hint_popup(tk_root, tmp_path):
    """Test _show_hint_popup creates and dismisses hint popup."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    assert viewer._hint_popup is None
    viewer._show_hint_popup()
    assert viewer._hint_popup is not None
    viewer._dismiss_hint_popup()
    assert viewer._hint_popup is None


def test_show_hint_popup_disabled(tk_root, tmp_path):
    """Test _show_hint_popup does nothing when hints disabled."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._hints_enabled = False
    viewer._show_hint_popup()
    assert viewer._hint_popup is None


def test_show_config_dialog_exists(tk_root, tmp_path):
    """Test configuration dialog method exists and can be called."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    assert hasattr(viewer, "_show_config")
    assert callable(viewer._show_config)

    import tkinter as tk
    from unittest.mock import patch

    def immediate_destroy(self):
        self.destroy()

    with patch.object(tk.Toplevel, "wait_window", immediate_destroy):
        viewer._show_config()
        assert viewer._dialog_active is False
