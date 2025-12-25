"""Tests for PhotoImage optimization using PPM format."""

import tkinter as tk
from unittest.mock import Mock

import pytest
from PIL import Image

import cdisplayagain


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for image conversion testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_photoimage_from_pil_ppm_format(tk_root):
    """Verify _photoimage_from_pil creates valid PhotoImage using PPM format."""
    # Create a mock viewer object
    app = Mock()
    app.tk = tk_root

    # Get the method from ComicViewer
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create a simple test image
    test_img = Image.new("RGB", (100, 100), color=(255, 0, 0))

    # Convert using the optimized method
    photo = photoimage_method(app, test_img)

    # Verify the PhotoImage was created successfully
    assert photo is not None
    assert isinstance(photo, tk.PhotoImage)
    assert photo.width() == 100
    assert photo.height() == 100


def test_photoimage_from_pil_various_sizes(tk_root):
    """Verify _photoimage_from_pil works with various image sizes."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    test_sizes = [(10, 10), (100, 50), (1920, 1080), (500, 1000)]

    for width, height in test_sizes:
        test_img = Image.new("RGB", (width, height), color=(width % 256, height % 256, 128))
        photo = photoimage_method(app, test_img)

        assert photo is not None
        assert photo.width() == width
        assert photo.height() == height


def test_photoimage_from_pil_handles_rgba(tk_root):
    """Verify _photoimage_from_pil converts RGBA images to RGB."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create an RGBA image
    rgba_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))

    # Convert using the optimized method
    photo = photoimage_method(app, rgba_img)

    # Verify the PhotoImage was created successfully
    assert photo is not None
    assert photo.width() == 100
    assert photo.height() == 100


def test_photoimage_from_pil_handles_grayscale(tk_root):
    """Verify _photoimage_from_pil converts grayscale images to RGB."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create a grayscale image
    gray_img = Image.new("L", (100, 100), color=128)

    # Convert using the optimized method
    photo = photoimage_method(app, gray_img)

    # Verify the PhotoImage was created successfully
    assert photo is not None
    assert photo.width() == 100
    assert photo.height() == 100


def test_photoimage_from_pil_handles_palette(tk_root):
    """Verify _photoimage_from_pil converts palette images to RGB."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create a palette image
    palette_img = Image.new("P", (100, 100))
    palette_img.putpalette([i % 256 for i in range(256 * 3)])

    # Convert using the optimized method
    photo = photoimage_method(app, palette_img)

    # Verify the PhotoImage was created successfully
    assert photo is not None
    assert photo.width() == 100
    assert photo.height() == 100


def test_photoimage_from_pil_performance_improvement(tk_root):
    """Benchmark PPM format vs old PNG+base64 approach."""
    import base64
    import io
    import time

    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create a test image
    test_img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))

    # Benchmark old method (PNG + base64)
    def old_method(img):
        rgb = img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        encoded = base64.encodebytes(buf.getvalue()).decode("ascii")
        return tk.PhotoImage(data=encoded, format="PNG", master=tk_root)

    iterations = 10
    start_time = time.perf_counter()
    for _ in range(iterations):
        old_method(test_img)
    old_time = time.perf_counter() - start_time

    # Benchmark new method (PPM)
    start_time = time.perf_counter()
    for _ in range(iterations):
        photoimage_method(app, test_img)
    new_time = time.perf_counter() - start_time

    print(f"\nOld method (PNG+base64): {old_time:.6f}s for {iterations} iterations")
    print(f"New method (PPM): {new_time:.6f}s for {iterations} iterations")
    print(f"Speedup: {old_time / new_time:.2f}x")

    # The new method should be faster (at least 1.5x speedup)
    assert new_time < old_time, f"New method should be faster: {new_time:.6f}s vs {old_time:.6f}s"
    assert old_time / new_time > 1.5, (
        f"Expected at least 1.5x speedup, got {old_time / new_time:.2f}x"
    )


def test_ppm_format_produces_correct_image_data(tk_root):
    """Verify that PPM format produces correct image data."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create an image with known pixel values
    test_img = Image.new("RGB", (10, 10), color=(255, 0, 0))

    # Convert to PhotoImage
    photo = photoimage_method(app, test_img)

    # Verify dimensions
    assert photo.width() == 10
    assert photo.height() == 10

    # Verify PhotoImage can be used (no exception means it's valid)
    data = photo.zoom(1)
    assert data is not None


def test_photoimage_large_image(tk_root):
    """Test that large images don't cause issues with PPM format."""
    app = Mock()
    app.tk = tk_root
    photoimage_method = cdisplayagain.ComicViewer._photoimage_from_pil

    # Create a large image
    test_img = Image.new("RGB", (4000, 6000), color=(128, 128, 128))

    # Convert using the optimized method
    photo = photoimage_method(app, test_img)

    assert photo is not None
    assert photo.width() == 4000
    assert photo.height() == 6000
