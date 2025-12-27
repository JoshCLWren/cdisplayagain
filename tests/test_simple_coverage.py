"""Additional simple coverage tests."""

from pathlib import Path
from unittest.mock import Mock, patch

import cdisplayagain


def _write_image(path: Path, size=(100, 100), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_log_key_event_no_widget(tk_root, tmp_path):
    """Test _log_key_event handles widget."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    event = Mock()
    event.keysym = "a"
    event.char = "a"
    event.keycode = 65
    event.state = 0
    event.widget = viewer

    viewer._log_key_event(event)


def test_show_help(tk_root, tmp_path):
    """Test _show_help displays help dialog."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    with patch("tkinter.messagebox.showinfo") as mock_showinfo:
        viewer._show_help()
        mock_showinfo.assert_called_once()


def test_dismiss_info_no_overlay(tk_root, tmp_path):
    """Test _dismiss_info does nothing when no overlay."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._info_overlay = None
    viewer._dismiss_info()


def test_show_context_menu_grab_release(tk_root, tmp_path):
    """Test _show_context_menu releases grab."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    with patch.object(viewer._context_menu, "grab_release") as mock_release:
        event = type("MockEvent", (), {"x_root": 100, "y_root": 100})()
        viewer._show_context_menu(event)
        mock_release.assert_called_once()


def test_update_title_no_source(tk_root, tmp_path):
    """Test _update_title when no source loaded."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None

    viewer._update_title()


def test_render_info_with_text_file(tk_root, tmp_path):
    """Test _render_info_with_image handles text file."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    info_path = tmp_path / "readme.txt"
    info_path.write_text("Sample text content")

    viewer.source = cdisplayagain.load_directory(tmp_path)
    viewer._current_index = 1

    viewer._render_info_with_image("readme.txt")
    assert viewer._info_overlay is not None
    viewer._dismiss_info()


def test_toggle_two_pages_method(tk_root, tmp_path):
    """Test toggle_two_pages method."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    initial = viewer._two_page_mode
    viewer.toggle_two_pages()
    assert viewer._two_page_mode is not initial
    viewer.toggle_two_pages()
    assert viewer._two_page_mode is initial


def test_execute_page_change(tk_root, tmp_path):
    """Test _execute_page_change executes action."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    called = [False]

    def test_action():
        called[0] = True

    viewer._execute_page_change(test_action)
    assert called[0] is True
