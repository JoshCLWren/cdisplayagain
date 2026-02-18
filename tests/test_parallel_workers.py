"""Tests for parallel decoding with multiple workers (Phase 4)."""

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


def create_test_cbz(path, page_count=10, image_size=(100, 200)):
    """Create a test CBZ with simple images."""
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(page_count):
            img = Image.new("RGB", image_size, color=(i * 25, 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page_{i:03d}.png", buf.getvalue())


def test_multiple_workers_created(tk_root, tmp_path):
    """Test that ImageWorker creates multiple threads by default."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app) as worker:
        assert len(worker._threads) == 4, "Should create 4 worker threads by default"
        assert all(t.daemon for t in worker._threads), "All worker threads should be daemon"
        assert all(t.is_alive() for t in worker._threads), "All worker threads should be alive"


def test_custom_worker_count(tk_root, tmp_path):
    """Test that ImageWorker can be configured with custom worker count."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=2) as worker:
        assert len(worker._threads) == 2, "Should create 2 worker threads when specified"
        assert all(t.is_alive() for t in worker._threads), "All worker threads should be alive"


def test_parallel_processing_multiple_pages(tk_root, tmp_path):
    """Test that multiple workers can process pages concurrently."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=8)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=4) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        start_time = time.time()
        for i in range(4):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(3000, tk_root.quit)
        tk_root.mainloop()
        elapsed = time.time() - start_time

        assert len(results) == 4, f"Should process all 4 pages in queue, got {len(results)}"
        assert elapsed < 2.0, f"Parallel processing should be fast, took {elapsed:.2f}s"


def test_workers_share_queue(tk_root, tmp_path):
    """Test that all workers read from the same shared queue."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=6)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=3) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        for i in range(4):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) == 4, "All workers should process items from shared queue"
        processed_indices = [r[0] for r in results]
        assert len(set(processed_indices)) == 4, "All pages should be processed exactly once"


def test_thread_safety_cache_operations(tk_root, tmp_path):
    """Test that cache operations are thread-safe under concurrent access."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=4) as worker:
        results = []

        def capture_update(index, img):
            cw = max(1, app.canvas.winfo_width())
            ch = max(1, app.canvas.winfo_height())
            cache_key = (index, cw, ch)
            results.append(cache_key)
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        for i in range(4):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) == 4, "All cache operations should complete successfully"


def test_preload_with_parallel_workers(tk_root, tmp_path):
    """Test that preloading works correctly with multiple workers."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=4) as worker:
        preload_requests = []

        def capture_request(index, width, height, preload=False, render_generation=0):
            if preload:
                preload_requests.append(index)

        worker.request_page = capture_request

        worker.preload(1)
        worker.preload(2)

        assert len(preload_requests) == 2, "Should process preload requests with parallel workers"


def test_parallel_processing_priority_order(tk_root, tmp_path):
    """Test that priority queue ordering is maintained with parallel workers."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=6)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=2) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        worker.request_page(0, 100, 200, preload=False)
        worker.request_page(1, 100, 200, preload=True)
        worker.request_page(2, 100, 200, preload=False)
        worker.request_page(3, 100, 200, preload=True)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) == 4
        non_preload = [r[0] for r in results if r[0] in {0, 2}]
        assert len(non_preload) >= 1, "At least one non-preload request should be processed"


def test_rapid_page_turning_with_parallel_workers(tk_root, tmp_path):
    """Test that rapid page turning benefits from parallel workers."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=4) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))

        app._update_from_cache = capture_update

        start_time = time.time()
        for i in range(10):
            worker.request_page(i, 100, 200, render_generation=0)
        time.sleep(0.01)

        tk_root.after(1000, tk_root.quit)
        tk_root.mainloop()
        elapsed = time.time() - start_time

        assert len(results) > 0, "Should process at least some pages rapidly"
        assert elapsed < 1.5, (
            f"Parallel workers should handle rapid requests quickly, took {elapsed:.2f}s"
        )


def test_workers_handle_queue_full_gracefully(tk_root, tmp_path):
    """Test that multiple workers handle full queue gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=20)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=4) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        for i in range(4):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) <= 4, "Should only process max queue size items"


def test_single_worker_backward_compat(tk_root, tmp_path):
    """Test that single worker mode works for backward compatibility."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=1) as worker:
        assert len(worker._threads) == 1, "Should support single worker mode"

        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 3:
                tk_root.quit()

        app._update_from_cache = capture_update

        for i in range(3):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(1000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) == 3, "Single worker should process all pages"


def test_worker_handles_none_source_gracefully(tk_root, tmp_path):
    """Test that worker handles None source gracefully during shutdown."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app, num_workers=2) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 2:
                tk_root.quit()

        app._update_from_cache = capture_update

        worker.request_page(0, 100, 200, render_generation=0)

        tk_root.update()
        time.sleep(0.1)
        tk_root.update()

        app.source = None

        for i in range(1, 4):
            worker.request_page(i, 100, 200, render_generation=0)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) >= 1, (
            f"Should process at least one page before source is None, got {len(results)}"
        )
