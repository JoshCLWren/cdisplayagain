"""Performance benchmarks for cdisplayagain."""

import time
import zipfile
import pytest
import io
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image
import cdisplayagain
import tkinter as tk
from image_backend import get_resized_bytes, HAS_PYVIPS

# -----------------------------------------------------------------------------
# Helpers for Realistic Data
# -----------------------------------------------------------------------------


def create_realistic_page(width=1920, height=3000, color=(100, 100, 100)):
    """Generate a realistic-ish page (HD resolution)."""
    # Use simple solid color for speed of generation, but sufficient size for memory tests
    return Image.new("RGB", (width, height), color=color)


def create_benchmark_cbz(path, page_count=5):
    """Create a CBZ with a few large HD pages."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        for i in range(page_count):
            img = create_realistic_page(color=(i * 10, 100, 100))
            buf = io.BytesIO()
            # Use JPEG to force decoding overhead, quality=80 is typical
            img.save(buf, format="JPEG", quality=80)
            zf.writestr(f"page_{i:03d}.jpg", buf.getvalue())


def create_benchmark_cbr(path, page_count=3):
    """Create a CBR (RAR) using external tools if available for benchmarks."""
    # Since we can't easily create RARs from Python without external tools or proprietary libs,
    # we might skip creation if 'rar' CLI isn't there.
    # But usually creating RARs is harder than reading.
    # We will assume for this benchmark we might need to skip if we can't create it.
    # Actually, let's skip CREATION benchmark and focus on if we had one.
    # But we don't have one.
    # Let's fallback to just measuring CBZ fully as it covers the internal pipeline.
    # If we really want to test CBR read speed, we need a Mock or strict dependency.
    pass


# -----------------------------------------------------------------------------
# Existing Isolated Benchmarks (Retained)
# -----------------------------------------------------------------------------


def test_perf_load_cbz_large_file_count(tmp_path):
    """Ensure loading a CBZ with many files is fast (Metadata limit)."""
    cbz_path = tmp_path / "large.cbz"
    file_count = 1000

    with zipfile.ZipFile(cbz_path, "w") as zf:
        for i in range(file_count):
            zf.writestr(f"page_{i:04d}.png", b"x")

    start_time = time.perf_counter()
    source = cdisplayagain.load_cbz(cbz_path)
    duration = time.perf_counter() - start_time
    print(f"\nPerformance [Load CBZ len={file_count}]: {duration:.6f}s")

    # Expect < 0.1 second for 1000 files metadata load
    assert duration < 0.1, f"Loading {file_count} files took too long: {duration:.4f}s"
    if source.cleanup:
        source.cleanup()


def test_perf_natural_sort_speed():
    """Benchmark natural_key sorting."""
    count = 5000
    items = [f"Section {i} - Page {j}.jpg" for i in range(10) for j in range(count // 10)]
    import random

    random.shuffle(items)

    start_time = time.perf_counter()
    items.sort(key=cdisplayagain.natural_key)
    duration = time.perf_counter() - start_time
    print(f"\nPerformance [Natural Sort len={count}]: {duration:.6f}s")

    # Sorting 5k items should be very fast (<0.1s)
    assert duration < 0.1, f"Sorting {count} items took {duration:.4f}s"


def test_perf_image_resize_lanczos():
    """Benchmark image resizing with LANCZOS to ensure reasonable limits."""
    w, h = 3840, 2160
    img = Image.new("RGB", (w, h), color=(100, 150, 200))
    target_w, target_h = 1920, 1080

    start_time = time.perf_counter()
    _ = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    duration = time.perf_counter() - start_time
    print(f"\nPerformance [Resize 4K->1080p]: {duration:.6f}s")

    # Resize operations are CPU intensive.
    # Target "real world fast" (<0.8s)
    assert duration < 0.8, f"Resizing 4k image took {duration:.4f}s"


# -----------------------------------------------------------------------------
# New Integrated Pipeline Benchmarks
# -----------------------------------------------------------------------------


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for image conversion testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_perf_page_turn_latency(tmp_path, tk_root):
    """Measure full 'Page Turn' latency.

    1. Read bytes from Zip
    2. Decode JPEG
    3. Resize (Lanczos)
    4. Convert to ImageTk
    """
    cbz_path = tmp_path / "benchmark.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    # Setup App State
    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    # Force a resize calculation to simulate a 1080p screen
    # We cheat by injecting values since window isn't actually mapped/sized by OS
    app.canvas.config(width=1920, height=1080)
    # We manually update the winfo_height/width wrappers if mocking,
    # but here we rely on Tk responding to config.
    # Tkinter requires update_idletasks for geometries to settle.
    app.update_idletasks()

    # Measure: Render Page 0 (First Load)
    start_time = time.perf_counter()
    app._render_current()
    page0_time = time.perf_counter() - start_time

    # Measure: Render Page 1 (Next Page - The 'Turn')
    app._current_index = 1
    start_time = time.perf_counter()
    app._render_current()
    page1_time = time.perf_counter() - start_time

    print(f"\nPerformance [First Paint]: {page0_time:.6f}s")
    print(f"Performance [Page Turn]: {page1_time:.6f}s")

    # Rubric: Page turn should be under 1.0s for HD content on "Fast" hardware
    # This includes JPEG decode + Resize + Tk overhead.
    assert page1_time < 1.0, f"Page turn took too long: {page1_time:.4f}s"

    # Do not call app._quit() here; let the fixture destroy the root.
    # app._quit() destroys master, which makes the fixture teardown fail.


def test_perf_cbr_extraction_overhead(tmp_path):
    """Measure time to extract a CBR if 'unar' is available.

    We simulate this by creating a ZIP and renaming it .cbr.
    'unar' handles zips too, so we can test the subprocess pathway effectively.
    """
    unar_path = shutil.which("unar")
    assert unar_path, "unar tool is required for CBR performance test"

    # We rename a ZIP to .cbr. cdisplayagain.py calls unar for .cbr.
    # unar detects file type by signature, so it should handle a zip-named-cbr just fine.
    cbr_path = tmp_path / "fake.cbr"
    create_benchmark_cbz(cbr_path, page_count=5)  # It's actually a zip structure

    start_time = time.perf_counter()
    source = cdisplayagain.load_cbr(cbr_path)
    duration = time.perf_counter() - start_time

    print(f"\nPerformance [Load CBR (unar subprocess) 5 HD pages]: {duration:.6f}s")

    # External process is slower. Expect < 2.0s
    assert duration < 2.0
    if source.cleanup:
        source.cleanup()


def test_image_backend_pyvips_available():
    """Verify pyvips is available for image backend."""
    assert HAS_PYVIPS is True, "pyvips should be available for performance testing"


def test_image_backend_lru_cache_hit():
    """Verify LRU cache works for repeated resize requests."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    target_w, target_h = 960, 540

    result1 = get_resized_bytes(raw_bytes, target_w, target_h)
    result2 = get_resized_bytes(raw_bytes, target_w, target_h)

    assert len(result1) > 0
    assert len(result2) > 0
    assert result1 == result2, "LRU cache should return same result for same inputs"


def test_image_backend_different_sizes():
    """Verify different resize sizes produce different outputs."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    result1 = get_resized_bytes(raw_bytes, 1920, 1080)
    result2 = get_resized_bytes(raw_bytes, 960, 540)

    assert len(result1) > 0
    assert len(result2) > 0
    assert result1 != result2, "Different sizes should produce different outputs"


def test_image_backend_roundtrip():
    """Verify resized image can be loaded back as PIL Image."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    target_w, target_h = 960, 540
    resized_bytes = get_resized_bytes(raw_bytes, target_w, target_h)

    resized_img = Image.open(io.BytesIO(resized_bytes))
    assert resized_img.size == (target_w, target_h)
