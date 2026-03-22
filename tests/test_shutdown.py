"""Tests for worker thread shutdown and cleanup."""

import time
import tkinter as tk
import zipfile

import pytest
from PIL import Image

import cdisplayagain


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for testing."""
    root = tk.Tk()
    root.withdraw()
    root.geometry("800x600")
    root.update()
    yield root
    root.destroy()


def create_test_cbz(path, page_count=5, image_size=(800, 1200)):
    """Create a test CBZ with images."""
    import io

    with zipfile.ZipFile(path, "w") as zf:
        for _i in range(page_count):
            img = Image.new("RGB", image_size, color=(_i * 50, 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            zf.writestr(f"page_{_i:03d}.jpg", buf.getvalue())


def test_shutdown_during_active_processing(tk_root, tmp_path):
    """Test that shutdown works correctly when workers are actively processing."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = app._worker

    for i in range(8):
        worker.request_page(i, 800, 600)

    time.sleep(0.1)

    app.cleanup()

    worker_threads = [
        t
        for t in __import__("threading").enumerate()
        if t.is_alive() and t.name.startswith("ImageWorker-")
    ]

    assert len(worker_threads) == 0, (
        f"All worker threads should have exited, but {len(worker_threads)} are still alive"
    )


def test_multiple_rapid_shutdown_cycles(tk_root, tmp_path):
    """Test rapid open/close cycles don't leave behind threads."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    initial_thread_count = len(
        [t for t in __import__("threading").enumerate() if t.name.startswith("ImageWorker-")]
    )

    for _ in range(5):
        app = cdisplayagain.ComicViewer(tk_root, cbz_path)
        app.update()
        worker = app._worker
        worker.request_page(0, 800, 600)
        time.sleep(0.05)
        app.cleanup()

    final_thread_count = len(
        [t for t in __import__("threading").enumerate() if t.name.startswith("ImageWorker-")]
    )

    assert final_thread_count == initial_thread_count, (
        f"Thread count changed from {initial_thread_count} to {final_thread_count} - "
        f"leaked {final_thread_count - initial_thread_count} threads"
    )

    for _ in range(5):
        app = cdisplayagain.ComicViewer(tk_root, cbz_path)
        app.update()
        worker = app._worker
        worker.request_page(0, 800, 600)
        time.sleep(0.05)
        app.cleanup()

    final_thread_count = len(
        [t for t in __import__("threading").enumerate() if t.name.startswith("ImageWorker-")]
    )

    assert final_thread_count == initial_thread_count, (
        f"Thread count changed from {initial_thread_count} to {final_thread_count} - "
        f"leaked {final_thread_count - initial_thread_count} threads"
    )


def test_worker_stop_preserves_app_reference_during_join(tk_root, tmp_path):
    """Test that stop() preserves app reference to avoid use-after-free crashes."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = app._worker

    worker.request_page(0, 800, 600)
    time.sleep(0.1)

    app_ref_before_stop = worker._app
    assert app_ref_before_stop is not None, "Worker should have app reference before stop"

    worker.stop()

    app_ref_after_stop = worker._app
    assert app_ref_after_stop is not None, (
        "Worker should NOT clear app reference after stop to prevent use-after-free"
    )


def test_blocking_put_nowait_doesnt_block_stop(tk_root, tmp_path):
    """Test that put_nowait in stop() doesn't block when queue is full."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=20)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = app._worker

    for i in range(20):
        worker.request_page(i, 800, 600)

    stop_start = time.time()
    worker.stop()
    stop_time = time.time() - stop_start

    assert stop_time < 2.0, f"stop() should complete quickly, took {stop_time:.3f}s"
    app.cleanup()
