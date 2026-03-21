"""Pytest fixtures shared across all test files."""

import logging
import threading
import time
import tkinter as tk

import pytest

import cdisplayagain


@pytest.fixture(autouse=True)
def cleanup_workers():
    """Clean up any leaked worker threads after each test."""
    yield
    cdisplayagain.ImageWorker.stop_all()

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
            "Worker threads failed to exit after 2 seconds: %s",
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
    root.destroy()
