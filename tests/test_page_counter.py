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
    """Test the coordinate sampling logic directly.

    Verifies that the luminance is sampled from the visible portion of the
    image at the counter's position, not the entire page average.
    """
    from PIL import Image, ImageStat

    def test_sampling(img, canvas_w, canvas_h, scroll_offset=0):
        """Simulate the _page_counter_color logic and return the sampled mean."""
        iw, ih = img.size
        cw, ch = canvas_w, canvas_h

        margin = 12
        counter_x = cw - margin
        counter_y = ch - margin

        image_left = (cw - iw) // 2
        image_top = (ch - ih) // 2 if ih <= ch else -scroll_offset

        img_x = counter_x - image_left
        img_y = counter_y - image_top

        if 0 <= img_x < iw and 0 <= img_y < ih:
            sample_size = 16
            left = max(0, img_x - sample_size)
            top = max(0, img_y - sample_size)
            right = min(iw, img_x + sample_size)
            bottom = min(ih, img_y + sample_size)
            region = img.crop((left, top, right, bottom)).convert("L")
            return ImageStat.Stat(region).mean[0]

        return None

    # Test 1: Image fills the canvas, white corner under counter
    # Dark page (800x600) with white bottom-right corner
    img1 = Image.new("RGB", (800, 600), color=(0, 0, 0))
    for x in range(750, 800):
        for y in range(550, 600):
            img1.putpixel((x, y), (255, 255, 255))
    mean1 = test_sampling(img1, 800, 600)
    assert mean1 is not None, "counter should be over the image"
    assert mean1 >= 128  # counter area is white -> black text

    # Test 2: Same image, dark corner under counter
    img2 = Image.new("RGB", (800, 600), color=(255, 255, 255))
    for x in range(750, 800):
        for y in range(550, 600):
            img2.putpixel((x, y), (0, 0, 0))
    mean2 = test_sampling(img2, 800, 600)
    assert mean2 is not None
    assert mean2 < 128  # counter area is dark -> white text

    # Test 3: Tall image scrolled to show bottom (white corner under counter)
    img3 = Image.new("RGB", (800, 1200), color=(0, 0, 0))
    for x in range(750, 800):
        for y in range(1150, 1200):
            img3.putpixel((x, y), (255, 255, 255))
    # Scrolled to bottom: image_top = -(scroll_offset)
    mean3 = test_sampling(img3, 800, 600, scroll_offset=600)
    assert mean3 is not None
    assert mean3 >= 128  # showing bottom of tall image with white corner

    # Test 4: Tall image scrolled to top (dark corner under counter)
    img4 = Image.new("RGB", (800, 1200), color=(255, 255, 255))
    for x in range(750, 800):
        for y in range(572, 604):
            img4.putpixel((x, y), (0, 0, 0))
    # Not scrolled: image_top = 0, counter at y=588 maps to img_y=588
    mean4 = test_sampling(img4, 800, 600, scroll_offset=0)
    assert mean4 is not None
    assert mean4 < 128  # dark corner at counter position
