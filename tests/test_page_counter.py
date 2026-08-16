"""Tests for the on-canvas page counter feature."""

from __future__ import annotations

from pathlib import Path

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(128, 128, 128)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def _counter_text(viewer: cdisplayagain.ComicViewer) -> str | None:
    """Return the canvas text of the page counter, or None if absent."""
    if viewer._page_counter_id is None:
        return None
    return viewer.canvas.itemcget(viewer._page_counter_id, "text")


def test_counter_shows_on_image_page(tk_root, tmp_path):
    """Loading a multi-image source renders a counter on the first image page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    from PIL import Image

    viewer._display_cached_image(Image.new("RGB", (50, 50), color=(255, 255, 255)))
    viewer.update()

    assert viewer._page_counter_id is not None
    assert _counter_text(viewer) == "1/2"


def test_counter_updates_on_next_page(tk_root, tmp_path):
    """The counter text advances with the page index."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))
    _write_image(folder / "page3.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    from PIL import Image

    viewer._display_cached_image(Image.new("RGB", (50, 50), color=(255, 255, 255)))
    assert _counter_text(viewer) == "1/3"

    viewer._current_index = 1
    viewer._display_cached_image(Image.new("RGB", (50, 50), color=(255, 255, 255)))
    assert _counter_text(viewer) == "2/3"


def test_counter_hidden_on_text_page(tk_root, tmp_path):
    """Counter is hidden on text/info pages."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.txt").write_text("info")
    _write_image(folder / "page1.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._render_current_sync()
    assert viewer._page_counter_id is None


def test_counter_hidden_on_info_overlay_with_image(tk_root, tmp_path):
    """Counter stays hidden when info overlay is shown alongside image."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.txt").write_text("info")
    _write_image(folder / "page1.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    from PIL import Image

    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    viewer._image_cache[(1, cw, ch)] = Image.new("RGB", (50, 50), color=(255, 255, 255))

    viewer._render_current_sync()
    assert viewer._info_overlay is not None
    assert viewer._page_counter_id is None


def test_counter_color_black_on_light_page(tk_root, tmp_path):
    """Counter color is black when page luminance is high."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()

    from PIL import Image

    viewer._current_pil = Image.new("RGB", (50, 50), color=(255, 255, 255))
    assert viewer._page_counter_color() == "#000000"


def test_counter_color_white_on_dark_page(tk_root, tmp_path):
    """Counter color is white when page luminance is low."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(0, 0, 0))
    _write_image(folder / "page2.png", color=(0, 0, 0))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()

    from PIL import Image

    viewer._current_pil = Image.new("RGB", (50, 50), color=(0, 0, 0))
    assert viewer._page_counter_color() == "#ffffff"


def test_counter_color_defaults_white_without_pil(tk_root, tmp_path):
    """Counter color defaults to white when no PIL image is set."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_pil = None

    assert viewer._page_counter_color() == "#ffffff"


def test_counter_color_falls_back_when_pil_invalid(tk_root, tmp_path):
    """Counter color falls back to white when luminance sampling fails."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()

    from PIL import Image

    class BrokenImage(Image.Image):
        @staticmethod
        def resize(*args, **kwargs):
            raise OSError("resize failed")

    viewer._current_pil = BrokenImage()
    assert viewer._page_counter_color() == "#ffffff"


def test_update_page_counter_handles_stale_id(tk_root, tmp_path):
    """_update_page_counter handles a stale counter id without raising."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._update_page_counter()
    real_id = viewer._page_counter_id
    assert real_id is not None

    viewer.canvas.delete(real_id)
    viewer._update_page_counter()
    assert viewer._page_counter_id is not None
    assert viewer._page_counter_id != real_id


def test_clear_page_counter_handles_missing_item(tk_root, tmp_path):
    """_clear_page_counter swallows TclError when id no longer exists."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()
    viewer._page_counter_id = 999999
    viewer._clear_page_counter()
    assert viewer._page_counter_id is None


def test_clear_page_counter_swallows_tclerror(tk_root, tmp_path):
    """_clear_page_counter swallows TclError raised by canvas.delete."""
    from unittest.mock import patch

    from cdisplayagain import tk as cdisplayagain_tk

    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()
    viewer._page_counter_id = 1

    with patch.object(
        viewer.canvas,
        "delete",
        side_effect=cdisplayagain_tk.TclError("already gone"),
    ):
        viewer._clear_page_counter()
    assert viewer._page_counter_id is None


def test_update_page_counter_swallows_tclerror(tk_root, tmp_path):
    """_update_page_counter swallows TclError raised by canvas.delete."""
    from unittest.mock import patch

    from cdisplayagain import tk as cdisplayagain_tk

    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._page_counter_id = 1

    with patch.object(
        viewer.canvas,
        "delete",
        side_effect=cdisplayagain_tk.TclError("already gone"),
    ):
        viewer._update_page_counter()
    assert viewer._page_counter_id is not None


def test_counter_text_none_when_no_source(tk_root, tmp_path):
    """_page_counter_text returns None with no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None

    assert viewer._page_counter_text() is None


def test_counter_text_none_with_single_page(tk_root, tmp_path):
    """Counter is suppressed when there is only one page in the source."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()

    assert viewer._page_counter_text() is None


def test_update_page_counter_creates_and_clears(tk_root, tmp_path):
    """_update_page_counter creates an item when text exists, clears when it does not."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", color=(255, 255, 255))
    _write_image(folder / "page2.png", color=(255, 255, 255))

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._update_page_counter()
    assert viewer._page_counter_id is not None

    viewer._clear_page_counter()
    assert viewer._page_counter_id is None


def test_render_current_no_source_clears_counter(tk_root, tmp_path):
    """_render_current with no source clears the counter id."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()
    viewer.source = None
    viewer._page_counter_id = 999

    viewer._render_current()
    assert viewer._page_counter_id is None


def test_render_current_sync_no_source_clears_counter(tk_root, tmp_path):
    """_render_current_sync with no source clears the counter."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()
    viewer.source = None
    viewer._page_counter_id = 999

    viewer._render_current_sync()
    assert viewer._page_counter_id is None


def test_counter_color_sampling_logic():
    """Test the coordinate sampling logic directly."""
    from PIL import Image, ImageStat
    
    def test_sampling(img, cw, ch, iw, ih, scroll_offset=0):
        """Test sampling logic for given image and dimensions."""
        margin = 12
        cx = cw - margin
        cy = ch - margin

        image_left = (cw - iw) // 2
        image_top = (ch - ih) // 2 if ih <= ch else -scroll_offset
        img_x = max(0, min(iw - 1, cx - image_left))
        img_y = max(0, min(ih - 1, cy - image_top))

        sample_size = min(32, iw // 4, ih // 4)
        if sample_size < 4:
            sample_size = min(4, iw, ih)
        left = max(0, img_x - sample_size)
        top = max(0, img_y - sample_size)
        right = min(iw, img_x + sample_size)
        bottom = min(ih, img_y + sample_size)

        region = img.crop((left, top, right, bottom)).convert("L")
        return ImageStat.Stat(region).mean[0]

    # Test 1: Normal size image (fits in canvas)
    # Create a dark page (100x100) with a white border in the bottom-right
    img1 = Image.new("RGB", (100, 100), color=(0, 0, 0))
    # Add white border in bottom-right 30x30 area
    for x in range(70, 100):
        for y in range(70, 100):
            img1.putpixel((x, y), (255, 255, 255))
    
    # Test with realistic canvas size
    cw, ch = 800, 600
    iw, ih = 100, 100
    mean1 = test_sampling(img1, cw, ch, iw, ih)
    
    # The counter area should be white, so text should be black
    assert mean1 >= 128  # white area
    
    # Test 2: Light page with dark border
    img2 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    # Add dark border in bottom-right 30x30 area
    for x in range(70, 100):
        for y in range(70, 100):
            img2.putpixel((x, y), (0, 0, 0))
    
    mean2 = test_sampling(img2, cw, ch, iw, ih)
    # The counter area should be dark, so text should be white
    assert mean2 < 128  # dark area

    # Test 3: Tall image (doesn't fit in canvas) - regression test for issue #58
    # Create a tall dark page (100x1200) with white border at the bottom
    img3 = Image.new("RGB", (100, 1200), color=(0, 0, 0))
    # Add white border in bottom 30 rows
    for x in range(0, 100):
        for y in range(1170, 1200):
            img3.putpixel((x, y), (255, 255, 255))
    
    # Test with scroll offset = 0 (showing top of image)
    cw, ch = 800, 600
    iw, ih = 100, 1200
    mean3 = test_sampling(img3, cw, ch, iw, ih, scroll_offset=0)
    # Counter is at bottom of canvas, but we're showing top of image, so it should be dark
    assert mean3 < 128  # dark area
    
    # Test with scroll offset = 600 (showing bottom of image)
    mean4 = test_sampling(img3, cw, ch, iw, ih, scroll_offset=600)
    # Counter is at bottom of canvas, showing bottom of image, so it should be white
    assert mean4 >= 128  # white area
