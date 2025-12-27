"""Test placeholder parity methods that return None."""

from pathlib import Path

import cdisplayagain


def _write_image(path: Path) -> None:
    """Write a test image file."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)


def test_placeholder_methods_return_none(tk_root, tmp_path):
    """Test all placeholder parity methods return None."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    placeholder_methods = [
        "set_one_page_mode",
        "set_two_page_mode",
        "toggle_color_balance",
        "toggle_yellow_reduction",
        "_show_hint_popup",
        "toggle_two_pages",
        "toggle_hints",
        "toggle_two_page_advance",
        "set_page_buffer",
        "set_background_color",
        "set_mouse_binding",
    ]

    for method_name in placeholder_methods:
        method = getattr(viewer, method_name)
        assert method() is None


def test_set_page_buffer_with_argument(tk_root, tmp_path):
    """Test set_page_buffer accepts and ignores argument."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    assert viewer.set_page_buffer(5) is None
    assert viewer.set_page_buffer(None) is None


def test_set_background_color_with_argument(tk_root, tmp_path):
    """Test set_background_color accepts and ignores argument."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    assert viewer.set_background_color("white") is None
    assert viewer.set_background_color("#000000") is None
    assert viewer.set_background_color(None) is None


def test_set_mouse_binding_with_argument(tk_root, tmp_path):
    """Test set_mouse_binding accepts and ignores argument."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    assert viewer.set_mouse_binding("left") is None
    assert viewer.set_mouse_binding("right") is None
    assert viewer.set_mouse_binding(None) is None
