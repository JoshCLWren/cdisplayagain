"""Pytest fixtures shared across all test files."""

import tkinter as tk

import pytest


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for image conversion testing."""
    root = tk.Tk()
    root.withdraw()
    root.geometry("800x600")
    root.update()
    yield root
    root.destroy()
