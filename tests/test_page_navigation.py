"""Tests for page navigation features."""

import io
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from cdisplayagain import ComicViewer


@pytest.fixture
def setup_viewer():
    """Set up a ComicViewer with a mock comic source."""
    root = tk.Tk()
    root.withdraw()

    test_img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_image_bytes = buf.getvalue()

    mock_source = Mock()
    mock_source.pages = ["page1.jpg", "page2.jpg", "page3.jpg"]
    mock_source.cleanup = None
    mock_source.get_bytes.return_value = valid_image_bytes

    mock_img = Mock()
    mock_img.mode = "RGB"
    mock_img.size = (100, 100)
    mock_img.resize.return_value = mock_img
    mock_img.convert.return_value = mock_img
    mock_img.save = lambda b, **kwargs: b.write(valid_image_bytes)

    with patch("cdisplayagain.load_comic") as mock_load:
        mock_load.return_value = mock_source

        with patch("PIL.Image.open") as mock_img_open:
            mock_img_open.return_value = mock_img

            root.overrideredirect(True)
            root.geometry("100x100+0+0")

            app = ComicViewer(root, Path("dummy.cbz"))
            app.focus_set()
            root.update()

            yield app, root

    root.destroy()


def test_page_down_advances_page(setup_viewer):
    """Verify that Page Down advances to the next page."""
    app, root = setup_viewer

    initial_index = app._current_index
    app.event_generate("<Next>")
    root.update()

    assert app._current_index == initial_index + 1


def test_page_up_goes_back(setup_viewer):
    """Verify that Page Up goes back to the previous page."""
    app, root = setup_viewer

    app._current_index = 2
    app.event_generate("<Prior>")
    root.update()

    assert app._current_index == 1


def test_page_down_at_end_does_nothing(setup_viewer):
    """Verify that Page Down at last page stays there."""
    app, root = setup_viewer

    app._current_index = len(app.source.pages) - 1
    app.event_generate("<Next>")
    root.update()

    assert app._current_index == len(app.source.pages) - 1


def test_page_up_at_start_does_nothing(setup_viewer):
    """Verify that Page Up at first page stays there."""
    app, root = setup_viewer

    app._current_index = 0
    app.event_generate("<Prior>")
    root.update()

    assert app._current_index == 0


def test_spacebar_advances_on_fit_page(setup_viewer):
    """Verify that Spacebar advances when page fits on screen."""
    app, root = setup_viewer

    app._scaled_size = (50, 50)
    app.canvas.winfo_height = Mock(return_value=100)
    initial_index = app._current_index
    app._space_advance()
    root.update()

    assert app._current_index == initial_index + 1


def test_spacebar_scrolls_then_advances(setup_viewer):
    """Verify that Spacebar scrolls tall page then advances."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app._scroll_offset = 0
    initial_index = app._current_index

    app.event_generate("<space>")
    root.update()

    assert app._scroll_offset > 0
    assert app._current_index == initial_index


def test_spacebar_advances_at_bottom(setup_viewer):
    """Verify that Spacebar advances when already at bottom."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app.canvas.winfo_height = Mock(return_value=100)
    app._scroll_offset = 400
    initial_index = app._current_index

    app._space_advance()
    root.update()

    assert app._current_index == initial_index + 1
    assert app._scroll_offset == 0


def test_mouse_wheel_delta_positive_scrolls_up(setup_viewer):
    """Verify positive mouse wheel delta scrolls up."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app._scroll_offset = 200

    event = Mock()
    event.delta = 120
    event.num = 0

    app._on_mouse_wheel(event)
    root.update()

    assert app._scroll_offset < 200


def test_mouse_wheel_delta_negative_scrolls_down(setup_viewer):
    """Verify negative mouse wheel delta scrolls down."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app._scroll_offset = 200

    event = Mock()
    event.delta = -120
    event.num = 0

    app._on_mouse_wheel(event)
    root.update()

    assert app._scroll_offset > 200


def test_mouse_wheel_button_4_scrolls_up(setup_viewer):
    """Verify Button-4 (Linux scroll up) scrolls up."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app._scroll_offset = 200

    event = Mock()
    event.delta = 0
    event.num = 4

    app._on_mouse_wheel(event)
    root.update()

    assert app._scroll_offset < 200


def test_mouse_wheel_button_5_scrolls_down(setup_viewer):
    """Verify Button-5 (Linux scroll down) scrolls down."""
    app, root = setup_viewer

    app._scaled_size = (100, 500)
    app._scroll_offset = 200

    event = Mock()
    event.delta = 0
    event.num = 5

    app._on_mouse_wheel(event)
    root.update()

    assert app._scroll_offset > 200


def test_mouse_wheel_on_fit_page_navigates_next(setup_viewer):
    """Verify mouse wheel on fitting page goes to next page."""
    app, root = setup_viewer

    app._scaled_size = (50, 50)
    app.canvas.winfo_height = Mock(return_value=100)
    initial_index = app._current_index

    event = Mock()
    event.delta = -120
    event.num = 0

    app._on_mouse_wheel(event)
    root.update()

    assert app._current_index == initial_index + 1


def test_mouse_wheel_back_on_fit_page_navigates_prev(setup_viewer):
    """Verify mouse wheel back on fitting page goes to previous page."""
    app, root = setup_viewer

    app._scaled_size = (50, 50)
    app.canvas.winfo_height = Mock(return_value=100)
    app._current_index = 1

    event = Mock()
    event.delta = 120
    event.num = 0

    app._on_mouse_wheel(event)
    root.update()

    assert app._current_index == 0
