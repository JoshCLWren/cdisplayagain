"""Benchmark parallel decoding performance."""

import io
import time
import tkinter as tk
import zipfile

import pytest
from PIL import Image

import cdisplayagain
from cdisplayagain import ImageWorker


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def create_large_test_cbz(path, page_count=20, image_size=(800, 1200)):
    """Create a test CBZ with larger images for realistic benchmarking."""
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(page_count):
            img = Image.new("RGB", image_size, color=(i * 10, 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page_{i:03d}.png", buf.getvalue())


def test_single_worker_vs_parallel_performance(tk_root, tmp_path):
    """Benchmark single worker vs parallel workers for page decoding."""
    cbz_path = tmp_path / "bench.cbz"
    create_large_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    results = []

    def capture_update(index, img):
        results.append((index, img.size))

    app._update_from_cache = capture_update

    worker_single = ImageWorker(app, num_workers=1)
    results.clear()

    start_single = time.time()
    for i in range(4):
        worker_single.request_page(i, 800, 600)

    tk_root.after(3000, tk_root.quit)
    tk_root.mainloop()
    time_single = time.time() - start_single

    results.clear()
    worker_parallel = ImageWorker(app, num_workers=4)

    start_parallel = time.time()
    for i in range(4):
        worker_parallel.request_page(i, 800, 600)

    tk_root.after(3000, tk_root.quit)
    tk_root.mainloop()
    time_parallel = time.time() - start_parallel

    print(f"\nSingle worker time: {time_single:.3f}s")
    print(f"Parallel workers time: {time_parallel:.3f}s")
    print(f"Speedup: {time_single / time_parallel:.2f}x")

    assert len(results) >= 1, "Should process at least one page"


def test_throughput_with_multiple_workers(tk_root, tmp_path):
    """Measure throughput when processing many pages."""
    cbz_path = tmp_path / "throughput.cbz"
    create_large_test_cbz(cbz_path, page_count=15)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    results = []

    def capture_update(index, img):
        results.append((index, img.size))

    app._update_from_cache = capture_update

    worker = ImageWorker(app, num_workers=4)

    start_time = time.time()
    for i in range(4):
        worker.request_page(i, 800, 600)

    tk_root.after(3000, tk_root.quit)
    tk_root.mainloop()
    elapsed = time.time() - start_time

    print(f"\nProcessed {len(results)} pages in {elapsed:.3f}s")
    print(f"Throughput: {len(results) / elapsed:.2f} pages/second")

    assert len(results) > 0, "Should process pages"
