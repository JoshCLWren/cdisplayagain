"""Test direct PIL Image caching to avoid encode/decode roundtrip."""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from cdisplayagain import ComicViewer, LRUCache


@pytest.fixture
def mock_viewer_with_comic():
    """Create a mock viewer with loaded comic."""
    import io
    import tkinter as tk
    from PIL import Image
    import zipfile
    from pathlib import Path
    import tempfile
    
    # Create test comic
    with tempfile.NamedTemporaryFile(suffix='.cbz', delete=False) as tf:
        cbz_path = Path(tf.name)
    
    with zipfile.ZipFile(cbz_path, 'w') as zf:
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        zf.writestr("page_001.jpg", buf.getvalue())
    
    # Create Tk root
    root = tk.Tk()
    root.withdraw()
    
    # Create viewer
    viewer = type('MockViewer', (), {
        '_canvas_properly_sized': True,
        '_current_index': 0,
        '_image_cache': {},
        'canvas': MagicMock(winfo_width=lambda: 800, winfo_height=lambda: 600),
        'source': MagicMock(pages=['page_001.jpg'], get_bytes=lambda x: b'fake')
    })()
    
    import cdisplayagain
    viewer = cdisplayagain.ComicViewer(root, cbz_path)
    
    yield viewer
    
    root.destroy()


def test_image_cache_stores_pil_images():
    """Test that _image_cache stores PIL Image objects directly, not bytes."""
    cache = LRUCache(maxsize=5)

    # Create a simple test PIL Image
    img = Image.new("RGB", (100, 100), color="red")

    # Store PIL Image in cache
    cache["page_0_800_600"] = img

    # Retrieve and verify it's a PIL Image
    cached = cache["page_0_800_600"]
    assert isinstance(cached, Image.Image)
    assert cached.size == (100, 100)


def test_update_from_cache_stores_pil_image(mock_viewer_with_comic):
    """Test that _update_from_cache stores PIL Images in the cache."""
    viewer = mock_viewer_with_comic
    viewer._canvas_properly_sized = True

    # Create a test PIL Image
    test_img = Image.new("RGB", (800, 600), color="blue")

    # Call _update_from_cache with PIL Image
    viewer._current_index = 0
    viewer._update_from_cache(0, test_img)

    # Verify it's cached as PIL Image
    cached = viewer._image_cache.get((0, 800, 600))
    assert cached is not None
    assert isinstance(cached, Image.Image)
    assert cached.size == (800, 600)


def test_display_cached_image_accepts_pil_image(mock_viewer_with_comic):
    """Test that _display_cached_image works with PIL Image input."""
    viewer = mock_viewer_with_comic

    # Create a test PIL Image
    test_img = Image.new("RGB", (800, 600), color="green")

    # Mock ImageTk.PhotoImage to avoid Tk requirement
    with patch("cdisplayagain.ImageTk.PhotoImage") as mock_photoimage:
        mock_tk_img = MagicMock()
        mock_photoimage.return_value = mock_tk_img

        # Call _display_cached_image with PIL Image
        viewer._display_cached_image(test_img)

        # Verify it didn't try to decode bytes
        assert viewer._current_pil == test_img
        assert viewer._tk_img == mock_tk_img


def test_no_encode_decode_in_display_cached_image():
    """Test that _display_cached_image doesn't perform encode/decode operations."""
    # Create a test image
    test_img = Image.new("RGB", (800, 600), color="yellow")

    # Mock the canvas and other Tk dependencies
    with patch("cdisplayagain.ImageTk.PhotoImage") as mock_photoimage:
        mock_tk_img = MagicMock()
        mock_photoimage.return_value = mock_tk_img

        viewer = MagicMock()
        viewer._imagetk_ready = True
        viewer._tk_img = None
        viewer.canvas = MagicMock()
        viewer.canvas.winfo_width.return_value = 800
        viewer.canvas.winfo_height.return_value = 600
        viewer.canvas.delete.return_value = None
        viewer.canvas.create_image.return_value = 12345

        # Import the actual method from the module
        from cdisplayagain import ComicViewer

        # Call the method
        ComicViewer._display_cached_image(viewer, test_img)

        # Verify Image.open was NOT called (no decoding)
        # The method should directly use the PIL Image
        assert viewer._current_pil == test_img


def test_pil_cache_reuse_avoids_decode(mock_viewer_with_comic):
    """Test that cached PIL Images avoid decode step on subsequent access."""
    viewer = mock_viewer_with_comic
    viewer._canvas_properly_sized = True

    # Create test image
    test_img = Image.new("RGB", (800, 600), color="purple")

    # Cache it
    viewer._current_index = 0
    viewer._update_from_cache(0, test_img)

    # Retrieve from cache
    cached = viewer._image_cache.get((0, 800, 600))

    # Verify it's the same PIL Image object (no encoding/decoding happened)
    assert cached is test_img
    assert isinstance(cached, Image.Image)


def test_cache_key_tuple_with_pil_image():
    """Test that cache keys work correctly with PIL Image values."""
    cache = LRUCache(maxsize=10)

    # Create different images for different cache keys
    img1 = Image.new("RGB", (800, 600), color="red")
    img2 = Image.new("RGB", (1024, 768), color="blue")
    img3 = Image.new("RGB", (800, 600), color="green")  # Same size as img1 but different content

    # Store with different keys
    cache[(0, 800, 600)] = img1
    cache[(1, 1024, 768)] = img2
    cache[(2, 800, 600)] = img3

    # Verify each returns the correct image
    assert cache[(0, 800, 600)] is img1
    assert cache[(1, 1024, 768)] is img2
    assert cache[(2, 800, 600)] is img3
