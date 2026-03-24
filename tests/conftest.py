"""Pytest fixtures shared across all test files."""

import gc
import logging
import threading
import time
import tkinter as tk
from unittest.mock import patch

import pytest
from PIL import Image

import cdisplayagain


@pytest.fixture(autouse=True)
def mock_image_processing():
    """Prevent pyvips/libvips from running in worker threads.

    Worker threads calling get_resized_pil trigger ORC (libvips's SIMD JIT),
    which probes CPU features via SIGILL. Python's faulthandler intercepts that
    SIGILL as fatal, crashing the process. Tests that need real pyvips import
    get_resized_pil directly from image_backend (unaffected by this patch).
    """

    def _fake_resize(_raw_bytes: bytes, target_width: int, target_height: int) -> Image.Image:
        return Image.new("RGB", (max(1, target_width), max(1, target_height)), color=(128, 128, 128))

    with patch("cdisplayagain.get_resized_pil", side_effect=_fake_resize):
        yield


@pytest.fixture(autouse=True)
def cleanup_workers():
    """Clean up any leaked worker threads after each test."""
    yield
    # Clean up after test
    cdisplayagain.ImageWorker.stop_all()
    gc.collect()  # Force GC in main thread so ComicViewer/worker cycles don't get collected in worker threads

    def get_worker_threads():
        return [
            t for t in threading.enumerate() if t.is_alive() and t.name.startswith("ImageWorker-")
        ]

    worker_threads = get_worker_threads()
    if worker_threads:
        logging.warning(
            "Found %d worker threads still alive after test cleanup: %s",
            len(worker_threads),
            [t.name for t in worker_threads],
        )

    for _ in range(20):
        worker_threads = get_worker_threads()
        if not worker_threads:
            break
        time.sleep(0.1)

    worker_threads = get_worker_threads()
    if worker_threads:
        logging.error(
            "Worker threads failed to exit after 5s: %s",
            [t.name for t in worker_threads],
        )


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for image conversion testing."""
    root = tk.Tk()
    root.withdraw()
    root.geometry("800x600")
    root.update()
    yield root
    cdisplayagain.ImageWorker.stop_all()
    root.update()
    root.destroy()
