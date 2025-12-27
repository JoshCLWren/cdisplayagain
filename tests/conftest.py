"""Pytest fixtures shared across all test files."""

import tkinter as tk

import pytest

import cdisplayagain


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for image conversion testing."""
    root = tk.Tk()
    root.withdraw()
    root.geometry("800x600")
    root.update()
    yield root
    root.destroy()


@pytest.fixture
def image_worker():
    """Provide an ImageWorker that is properly stopped after tests."""

    class MockApp:
        def __init__(self):
            self.source = None
            self._render_generation = 0

        def after_idle(self, callback):
            pass

    workers = []
    mock_app = MockApp()

    def create_worker(num_workers: int = 4):
        worker = cdisplayagain.ImageWorker(mock_app, num_workers=num_workers)
        workers.append(worker)
        return worker

    yield create_worker

    for worker in workers:
        worker.stop()
