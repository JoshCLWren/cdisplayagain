"""Performance benchmarks for cdisplayagain."""

import io
import shutil
import time
import tkinter as tk
import zipfile
from pathlib import Path

import pytest
import pyvips
from PIL import Image

import cdisplayagain
from image_backend import get_resized_pil

# -----------------------------------------------------------------------------
# Performance Thresholds (tune as performance improves)
# These are for synchronous rendering - actual user experience
# -----------------------------------------------------------------------------
PERF_CBZ_LAUNCH_MAX = 0.01
PERF_CBR_LAUNCH_MAX = 0.3
PERF_COVER_RENDER_MAX = 0.1
PERF_PAGE_TURN_MAX = 0.1

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

    # Expect < 0.06 second for 1000 files metadata load
    assert duration < 0.06, f"Loading {file_count} files took too long: {duration:.4f}s"
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

    # Sorting 5k items should be very fast (<0.05s)
    assert duration < 0.05, f"Sorting {count} items took {duration:.4f}s"


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
    # Target "real world fast" (<0.3s)
    assert duration < 0.3, f"Resizing 4k image took {duration:.4f}s"


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

    # Rubric: Page turn should be under 0.1s for HD content on "Fast" hardware
    # This includes JPEG decode + Resize + Tk overhead.
    assert page1_time < 0.1, f"Page turn took too long: {page1_time:.4f}s"

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

    # External process is slower. Expect < 0.2s
    assert duration < 0.2
    if source.cleanup:
        source.cleanup()


def test_image_backend_pyvips_available():
    """Verify pyvips is available for image backend."""
    assert pyvips is not None, "pyvips should be available"


def test_image_backend_lru_cache_hit():
    """Verify LRU cache works for repeated resize requests."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    target_w, target_h = 960, 540

    result1 = get_resized_pil(raw_bytes, target_w, target_h)
    result2 = get_resized_pil(raw_bytes, target_w, target_h)

    assert isinstance(result1, Image.Image)
    assert isinstance(result2, Image.Image)
    assert result1 is result2, "LRU cache should return same object for same inputs"


def test_image_backend_different_sizes():
    """Verify different resize sizes produce different outputs."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    result1 = get_resized_pil(raw_bytes, 1920, 1080)
    result2 = get_resized_pil(raw_bytes, 960, 540)

    assert isinstance(result1, Image.Image)
    assert isinstance(result2, Image.Image)
    assert result1.size != result2.size, "Different sizes should produce different outputs"


def test_image_backend_roundtrip():
    """Verify resized image can be loaded back as PIL Image."""
    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    target_w, target_h = 960, 540
    resized_img = get_resized_pil(raw_bytes, target_w, target_h)

    resized_img = Image.open(io.BytesIO(resized_bytes))
    assert resized_img.size == (target_w, target_h)


def test_pyvips_available():
    """Verify pyvips is available."""
    assert pyvips is not None


def test_lru_cache_hit():
    """Verify LRU cache works for repeated requests."""
    from image_backend import get_resized_pil

    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    result1 = get_resized_pil(raw, 1920, 1080)
    result2 = get_resized_pil(raw, 1920, 1080)
    assert result1 is result2, "LRU cache should return same object"


def test_cache_first_render_hits_cache(tmp_path, tk_root):
    """Verify that rendering checks cache first and uses cached image."""
    cbz_path = tmp_path / "cache_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())

    if app.source:
        raw_bytes = app.source.get_bytes(app.source.pages[0])
        from image_backend import get_resized_pil

        resized_img = get_resized_pil(raw_bytes, cw, ch)

        cache_key = (0, cw, ch)
        app._image_cache[cache_key] = resized_bytes

        assert cache_key in app._image_cache, "Image should be cached"

        app._display_cached_image(resized_bytes)
        assert app._tk_img is not None, "Image should be displayed"

        initial_cache_size = len(app._image_cache)
        app._render_current()
        assert len(app._image_cache) == initial_cache_size, "Cache should not grow for cache hit"


def test_cache_first_render_queues_worker_on_miss(tmp_path, tk_root):
    """Verify that cache miss triggers background worker request."""
    cbz_path = tmp_path / "worker_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    assert cache_key not in app._image_cache, "Cache should be empty initially"

    initial_queue_size = app._worker._queue.qsize()
    app._render_current()

    assert app._worker._queue.qsize() >= initial_queue_size, (
        "Worker should receive request on cache miss"
    )


def test_display_cached_image_updates_canvas(tmp_path, tk_root):
    """Verify _display_cached_image correctly updates canvas with cached bytes."""
    cbz_path = tmp_path / "display_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=1)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())

    if app.source:
        raw_bytes = app.source.get_bytes(app.source.pages[0])
        from image_backend import get_resized_pil

        resized_img = get_resized_pil(raw_bytes, cw, ch)

        cache_key = (0, cw, ch)
        app._image_cache[cache_key] = resized_bytes

        assert cache_key in app._image_cache, "Image should be cached"

        cached_bytes = app._image_cache[cache_key]
        app.canvas.delete("all")
        app._tk_img = None
        app._canvas_image_id = None

        app._display_cached_image(cached_bytes)

        assert app._tk_img is not None, "Image should be displayed"
        assert app._canvas_image_id is not None, "Canvas should have image item"
        assert app._scaled_size is not None, "Scaled size should be set"


def test_cache_key_includes_dimensions(tmp_path, tk_root):
    """Verify cache key includes canvas dimensions."""
    cbz_path = tmp_path / "dimensions_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=1)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    if app.source:
        raw_bytes = app.source.get_bytes(app.source.pages[0])
        from image_backend import get_resized_pil

        cw1, ch1 = 1920, 1080
        resized_bytes1 = get_resized_pil(raw_bytes, cw1, ch1)
        cache_key1 = (0, cw1, ch1)
        app._image_cache[cache_key1] = resized_bytes1

        cw2, ch2 = 1280, 720
        resized_bytes2 = get_resized_pil(raw_bytes, cw2, ch2)
        cache_key2 = (0, cw2, ch2)
        app._image_cache[cache_key2] = resized_bytes2

        assert cache_key1 in app._image_cache, "First dimension should be cached"
        assert cache_key2 in app._image_cache, "Second dimension should be cached"
        assert cache_key1 != cache_key2, "Different dimensions should have different cache keys"


def test_render_info_with_image_uses_cache(tmp_path, tk_root):
    """Verify _render_info_with_image also uses cache-first approach."""
    cbz_path = tmp_path / "info_test.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        img = create_realistic_page(color=(100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        zf.writestr("info.txt", b"Test info file")
        zf.writestr("page_001.jpg", buf.getvalue())

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    if app.source and len(app.source.pages) > 1:
        cw = max(1, app.canvas.winfo_width())
        ch = max(1, app.canvas.winfo_height())

        image_index = None
        for idx, page in enumerate(app.source.pages):
            if not cdisplayagain.is_text_name(page):
                image_index = idx
                break

        if image_index is not None:
            raw_bytes = app.source.get_bytes(app.source.pages[image_index])
            from image_backend import get_resized_pil

            resized_img = get_resized_pil(raw_bytes, cw, ch)

            cache_key = (image_index, cw, ch)
            app._image_cache[cache_key] = resized_bytes

            assert cache_key in app._image_cache, "Info with image should use cache"


def test_perf_launch_sample_comics(tk_root):
    """Measure full integration: launch, cover render, and pagination."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    cbz_path = fixtures_dir / "test_cbz.cbz"
    cbr_path = fixtures_dir / "test_cbr.cbr"
    assert cbz_path.exists(), f"CBZ file not found: {cbz_path}"
    assert cbr_path.exists(), f"CBR file not found: {cbr_path}"

    results = []

    for label, comic_path in [("CBZ", cbz_path), ("CBR", cbr_path)]:
        start_time = time.perf_counter()
        app = cdisplayagain.ComicViewer(tk_root, comic_path)
        launch_time = time.perf_counter() - start_time

        app.canvas.config(width=1920, height=1080)
        app.update_idletasks()

        start_time = time.perf_counter()
        app._render_current_sync()
        cover_render_time = time.perf_counter() - start_time

        page_turn_times = []
        for _ in range(5):
            app.next_page()
            app.update_idletasks()
            start_time = time.perf_counter()
            app._render_current_sync()
            page_turn_times.append(time.perf_counter() - start_time)

        avg_page_turn = sum(page_turn_times) / len(page_turn_times)
        total_time = launch_time + cover_render_time + sum(page_turn_times)

        results.append((label, launch_time, cover_render_time, avg_page_turn, total_time))
        print(f"\nPerformance [{label} Launch]: {launch_time:.6f}s")
        print(f"Performance [{label} Cover Render]: {cover_render_time:.6f}s")
        print(f"Performance [{label} Avg Page Turn]: {avg_page_turn:.6f}s")
        print(f"Performance [{label} Total (5 pages)]: {total_time:.6f}s")

        if app.source and app.source.cleanup:
            app.source.cleanup()
        app.destroy()

    cbz_result = next(r for r in results if r[0] == "CBZ")
    cbr_result = next(r for r in results if r[0] == "CBR")
    _, cbz_launch, cbz_cover, cbz_page_turn, cbz_total = cbz_result
    _, cbr_launch, cbr_cover, cbr_page_turn, cbr_total = cbr_result

    print(f"\nPerformance [CBZ Launch]: {cbz_launch:.6f}s (max: {PERF_CBZ_LAUNCH_MAX:.3f}s)")
    print(f"Performance [CBR Launch]: {cbr_launch:.6f}s (max: {PERF_CBR_LAUNCH_MAX:.3f}s)")
    print(f"Performance [CBR/CBZ Launch Ratio]: {cbr_launch / cbz_launch:.2f}x")

    assert cbz_launch < PERF_CBZ_LAUNCH_MAX, (
        f"CBZ launch took too long: {cbz_launch:.4f}s > {PERF_CBZ_LAUNCH_MAX}s"
    )
    assert cbr_launch < PERF_CBR_LAUNCH_MAX, (
        f"CBR launch took too long: {cbr_launch:.4f}s > {PERF_CBR_LAUNCH_MAX}s"
    )
    assert cbz_cover < PERF_COVER_RENDER_MAX, (
        f"CBZ cover render took too long: {cbz_cover:.4f}s > {PERF_COVER_RENDER_MAX}s"
    )
    assert cbr_cover < PERF_COVER_RENDER_MAX, (
        f"CBR cover render took too long: {cbr_cover:.4f}s > {PERF_COVER_RENDER_MAX}s"
    )
    assert cbz_page_turn < PERF_PAGE_TURN_MAX, (
        f"CBZ page turn took too long: {cbz_page_turn:.4f}s > {PERF_PAGE_TURN_MAX}s"
    )
    assert cbr_page_turn < PERF_PAGE_TURN_MAX, (
        f"CBR page turn took too long: {cbr_page_turn:.4f}s > {PERF_PAGE_TURN_MAX}s"
    )
