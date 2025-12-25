"""Tests for threading architecture (Phase 3)."""

import io
import time
import tkinter as tk
import zipfile

import pytest
from PIL import Image

import cdisplayagain
from cdisplayagain import Debouncer, ImageWorker


@pytest.fixture
def tk_root():
    """Provide a headless Tk root for testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_debouncer_basic(tk_root):
    """Test that debouncer delays callback execution."""
    calls = []

    def callback():
        calls.append(1)

    debouncer = Debouncer(100, callback, tk_root)
    debouncer.trigger()

    assert len(calls) == 0, "Callback should not fire immediately"

    tk_root.after(150, tk_root.quit)
    tk_root.mainloop()

    assert len(calls) == 1, "Callback should fire after delay"


def test_debouncer_reset(tk_root):
    """Test that triggering again resets the delay."""
    calls = []

    def callback():
        calls.append(time.time())

    debouncer = Debouncer(100, callback, tk_root)
    debouncer.trigger()

    time.sleep(0.05)
    debouncer.trigger()

    tk_root.after(150, tk_root.quit)
    start = time.time()
    tk_root.mainloop()
    elapsed = time.time() - start

    assert len(calls) == 1, "Callback should fire only once"
    assert elapsed >= 0.1, "Second trigger should have reset the delay"


def test_debouncer_multiple_args(tk_root):
    """Test debouncer with callback arguments."""
    calls = []

    def callback(x, y):
        calls.append((x, y))

    debouncer = Debouncer(50, callback, tk_root)
    debouncer.trigger("a", "b")

    tk_root.after(100, tk_root.quit)
    tk_root.mainloop()

    assert calls == [("a", "b")]


def create_test_cbz(path, page_count=3):
    """Create a test CBZ with simple images."""
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(page_count):
            img = Image.new("RGB", (100, 200), color=(i * 50, 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page_{i:03d}.png", buf.getvalue())


def test_image_worker_basic(tk_root, tmp_path):
    """Test ImageWorker processes pages in background."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = ImageWorker(app)

    results = []

    def capture_update(index, resized_bytes):
        results.append((index, len(resized_bytes)))
        if len(results) >= 1:
            tk_root.quit()

    app._update_from_cache = capture_update

    worker.request_page(0, 100, 200)

    tk_root.after(500, tk_root.quit)
    tk_root.mainloop()

    assert len(results) > 0, "Worker should process page"


def test_image_worker_queue_full(tk_root, tmp_path):
    """Test ImageWorker handles full queue gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = ImageWorker(app)

    results = []

    def capture_update(index, resized_bytes):
        results.append((index, len(resized_bytes)))
        if len(results) >= 4:
            tk_root.quit()

    app._update_from_cache = capture_update

    for i in range(10):
        worker.request_page(i, 100, 200)

    tk_root.after(2000, tk_root.quit)
    tk_root.mainloop()

    assert len(results) <= 4, "Worker should only process max queue size"


def test_image_worker_daemon(tk_root, tmp_path):
    """Test ImageWorker thread is daemon and doesn't block exit."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = ImageWorker(app)

    assert worker._thread.daemon, "Worker thread should be daemon"


def test_debouncer_with_action(tk_root):
    """Test debouncer works with navigation actions."""
    calls = []

    def next_action():
        calls.append("next")

    def prev_action():
        calls.append("prev")

    debouncer = Debouncer(50, lambda: None, tk_root)

    debouncer._callback = next_action
    debouncer.trigger()

    tk_root.after(100, tk_root.quit)
    tk_root.mainloop()

    assert calls == ["next"]


def test_debouncer_trigger_various_actions(tk_root):
    """Test debouncer executes various navigation actions."""
    results = []

    def mock_action(name):
        results.append(name)

    debouncer = Debouncer(50, mock_action, tk_root)

    debouncer.trigger("next")
    debouncer.trigger("prev")
    debouncer.trigger("first")

    tk_root.after(150, tk_root.quit)
    tk_root.mainloop()

    assert len(results) == 1
    assert results[0] == "first"


def test_navigation_triggers_use_debouncer(tk_root, tmp_path):
    """Test navigation trigger methods properly use debouncer."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    initial_index = app._current_index

    app._trigger_next()

    tk_root.after(200, tk_root.quit)
    tk_root.mainloop()

    assert app._current_index == initial_index + 1


def test_multiple_navigation_triggers_debounced(tk_root, tmp_path):
    """Test that multiple rapid navigation triggers are debounced."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    initial_index = app._current_index

    app._trigger_next()
    app._trigger_next()
    app._trigger_next()

    tk_root.after(250, tk_root.quit)
    tk_root.mainloop()

    assert app._current_index == initial_index + 1


def test_focus_restorer_multiple_schedules(tk_root):
    """Test FocusRestorer only schedules one refresh at a time."""
    calls = []

    def focus_fn():
        calls.append(1)

    restorer = cdisplayagain.FocusRestorer(tk_root.after_idle, focus_fn)

    restorer.schedule()
    restorer.schedule()
    restorer.schedule()

    tk_root.after(100, tk_root.quit)
    tk_root.mainloop()

    assert len(calls) == 1, "Should only call focus once despite multiple schedules"


def test_execute_page_change_action(tk_root, tmp_path):
    """Test _execute_page_change properly executes action."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    initial_index = app._current_index

    app._execute_page_change(lambda: app.next_page())

    tk_root.after(100, tk_root.quit)
    tk_root.mainloop()

    assert app._current_index == initial_index + 1


def test_update_from_cache_directly(tk_root, tmp_path):
    """Test _update_from_cache method processes resized bytes."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    img = Image.new("RGB", (100, 200), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    resized_bytes = buf.getvalue()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    app._canvas_properly_sized = True
    app._update_from_cache(0, resized_bytes)

    assert cache_key in app._image_cache
    assert app._tk_img is not None
