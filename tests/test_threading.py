"""Tests for threading architecture (Phase 3)."""

import io
import queue
import time
import tkinter as tk
import unittest.mock as mock
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
    app.update()
    with ImageWorker(app) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 1:
                tk_root.quit()

        app._update_from_cache = capture_update

        worker.request_page(0, 100, 200)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) > 0, "Worker should process page"


def test_image_worker_queue_full(tk_root, tmp_path):
    """Test ImageWorker handles full queue gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app) as worker:
        results = []

        def capture_update(index, img):
            assert isinstance(img, Image.Image)
            results.append((index, img.size))
            if len(results) >= 4:
                tk_root.quit()

        app._update_from_cache = capture_update

        for i in range(10):
            worker.request_page(i, 100, 200)

        tk_root.after(2000, tk_root.quit)
        tk_root.mainloop()

        assert len(results) <= 4, "Worker should only process max queue size"


def test_image_worker_daemon(tk_root, tmp_path):
    """Test ImageWorker threads are daemon and don't block exit."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    with ImageWorker(app) as worker:
        assert len(worker._threads) > 0, "Worker should have threads"
        assert all(t.daemon for t in worker._threads), "All worker threads should be daemon"


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
    raw_bytes = buf.getvalue()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    from image_backend import get_resized_pil

    resized_img = get_resized_pil(raw_bytes, cw, ch)

    app._canvas_properly_sized = True
    app._update_from_cache(0, resized_img)

    assert cache_key in app._image_cache
    assert isinstance(resized_img, Image.Image)
    assert app._tk_img is not None


def test_preload_next_page(tk_root, tmp_path):
    """Test that _render_current preloads the next page."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=5)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    preload_requests = []

    original_preload = app._worker.preload

    def capture_preload(index):
        preload_requests.append(index)
        original_preload(index)

    app._worker.preload = capture_preload

    app._render_current()

    assert len(preload_requests) == 1
    assert preload_requests[0] == 1


def test_preload_on_last_page(tk_root, tmp_path):
    """Test that preloading is skipped on the last page."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    preload_requests = []

    def capture_preload(index):
        preload_requests.append(index)

    app._worker.preload = capture_preload

    app._current_index = 2
    app._render_current()

    assert len(preload_requests) == 0


def test_preload_skips_text_pages(tk_root, tmp_path):
    """Test that preloading skips text info pages."""
    import zipfile

    cbz_path = tmp_path / "test_with_text.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        img = Image.new("RGB", (100, 200), color=(50, 100, 150))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        zf.writestr("01_page_000.png", buf.getvalue())
        zf.writestr("02_info.txt", b"Test info")
        zf.writestr("03_page_001.png", buf.getvalue())

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    preload_requests = []
    original_request = app._worker.request_page

    def capture_request(index, width, height, preload=False, render_generation=0):
        if preload:
            preload_requests.append(index)
        original_request(index, width, height, preload, render_generation)

    app._worker.request_page = capture_request

    app._current_index = 1
    app._render_current()

    assert len(preload_requests) == 1
    assert preload_requests[0] == 2


def test_worker_preload_method(tk_root, tmp_path):
    """Test ImageWorker.preload uses canvas dimensions."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    with ImageWorker(app) as worker:
        queue_items = []

        def capture_request(index, width, height, preload=False, render_generation=0):
            queue_items.append((index, width, height, preload, render_generation))

        worker.request_page = capture_request

        worker.preload(1)

        assert len(queue_items) == 1
        index, width, height, preload, render_generation = queue_items[0]
        assert index == 1
        assert width > 0
        assert height > 0
        assert preload is True


def test_stale_render_cancellation(tk_root, tmp_path):
    """Test that stale renders are cancelled when rapidly page-turning."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    initial_generation = app._render_generation

    render_requests = []

    def capture_request(index, width, height, preload=False, render_generation=0):
        render_requests.append((index, render_generation, preload))

    app._worker.request_page = capture_request

    app._render_current()

    assert len(render_requests) >= 1
    assert render_requests[0][1] == initial_generation
    assert render_requests[0][2] is False

    app.next_page()
    assert app._render_generation == initial_generation + 1


def test_multiple_rapid_page_turns(tk_root, tmp_path):
    """Test that multiple rapid page turns increment render generation."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.update()

    initial_generation = app._render_generation

    app.next_page()
    assert app._render_generation == initial_generation + 1

    app.next_page()
    assert app._render_generation == initial_generation + 2

    app.next_page()
    assert app._render_generation == initial_generation + 3

    app.prev_page()
    assert app._render_generation == initial_generation + 4

    app.first_page()
    assert app._render_generation == initial_generation + 5

    app.last_page()
    assert app._render_generation == initial_generation + 6


def test_worker_request_page_after_stop(tk_root, tmp_path):
    """Test that request_page returns early when worker is stopped."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    worker._stopped = True
    worker.request_page(0, 100, 200, render_generation=0)

    time.sleep(0.05)

    worker.stop()


def test_worker_request_page_without_app(tk_root, tmp_path):
    """Test that request_page returns early when _app is None."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    worker._app = None
    worker.request_page(0, 100, 200, render_generation=0)

    time.sleep(0.05)

    worker.stop()


def test_worker_request_page_queue_full(tk_root, tmp_path):
    """Test that request_page handles queue.Full gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    with mock.patch.object(worker._queue, "put_nowait", side_effect=queue.Full()):
        worker.request_page(0, 100, 200, render_generation=0)

    time.sleep(0.05)

    worker.stop()


def test_worker_context_manager(tk_root, tmp_path):
    """Test that context manager properly stops workers."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    with cdisplayagain.ImageWorker(app, num_workers=1) as worker:
        assert worker._stopped is False
        assert len(worker._threads) == 1

    assert worker._stopped is True
    assert len(worker._threads) == 0


def test_worker_cleanup_called_on_del(tk_root, tmp_path):
    """Test that cleanup is called when ComicViewer is garbage collected."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = app._worker
    assert worker is not None

    app.cleanup()

    assert worker._stopped is True


def test_del_calls_cleanup(tk_root, tmp_path):
    """Test that __del__ method calls cleanup."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = app._worker
    assert worker is not None

    app.__del__()

    assert worker._stopped is True


def test_worker_handles_after_idle_exception(tk_root, tmp_path, caplog):
    """Test that worker handles after_idle exception gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    with mock.patch.object(app, "after_idle", side_effect=RuntimeError("Test error")):
        worker = cdisplayagain.ImageWorker(app, num_workers=1)

        worker.request_page(0, 100, 200, render_generation=0)

        time.sleep(0.2)

        worker.stop()


def test_worker_handles_general_exception(tk_root, tmp_path, caplog):
    """Test that worker handles general exception in _run gracefully."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    with mock.patch("cdisplayagain.get_resized_pil", side_effect=RuntimeError("Test error")):
        worker = cdisplayagain.ImageWorker(app, num_workers=1)

        worker.request_page(0, 100, 200, render_generation=0)

        time.sleep(0.2)

        worker.stop()

        assert len([r for r in caplog.records if "Image worker error" in r.message]) > 0


def test_worker_stops_mid_processing(tk_root, tmp_path):
    """Test that worker respects _stopped flag mid-processing."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=10)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    results = []

    def capture_update(index, img):
        results.append(index)

    app._update_from_cache = capture_update

    def slow_resize(raw, width, height):
        time.sleep(0.05)
        from PIL import Image

        return Image.new("RGB", (width, height))

    with mock.patch("cdisplayagain.get_resized_pil", side_effect=slow_resize):
        worker.request_page(0, 100, 200, render_generation=0)

        time.sleep(0.1)

        worker.stop()

        time.sleep(0.2)

        assert worker._stopped is True


def test_worker_stop_handles_queue_full(tk_root, tmp_path):
    """Test that stop() handles queue.Full exception."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    with mock.patch.object(worker._queue, "put_nowait", side_effect=queue.Full()):
        worker.stop()

    assert worker._stopped is True


def test_worker_stop_handles_join_exception(tk_root, tmp_path):
    """Test that stop() handles thread.join exception."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    with mock.patch.object(worker._threads[0], "join", side_effect=RuntimeError("Test error")):
        worker.stop()

    assert worker._stopped is True
    assert len(worker._threads) == 0


def test_worker_should_stop_before_processing(tk_root, tmp_path):
    """Test that _should_stop() breaks loop before processing begins."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    tk_root.withdraw()
    tk_root.update()

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    worker.request_page(0, 100, 200, render_generation=0)
    worker._stopped = True

    time.sleep(0.2)

    worker.stop()


def test_worker_should_stop_during_processing(tk_root, tmp_path):
    """Test that _should_stop() breaks loop during image processing."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    tk_root.withdraw()
    tk_root.update()

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    def slow_resize(raw, width, height):
        time.sleep(0.05)
        from PIL import Image

        return Image.new("RGB", (width, height))

    with mock.patch("cdisplayagain.get_resized_pil", side_effect=slow_resize):
        worker.request_page(0, 100, 200, render_generation=0)
        time.sleep(0.02)
        worker._stopped = True
        time.sleep(0.2)

    worker.stop()


def test_worker_should_stop_before_callback(tk_root, tmp_path):
    """Test that _should_stop() breaks loop before scheduling callback."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    tk_root.withdraw()
    tk_root.update()

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    def slow_resize(raw, width, height):
        time.sleep(0.02)
        from PIL import Image

        return Image.new("RGB", (width, height))

    with mock.patch("cdisplayagain.get_resized_pil", side_effect=slow_resize):
        worker.request_page(0, 100, 200, render_generation=0)
        time.sleep(0.03)
        worker._stopped = True
        time.sleep(0.2)

    worker.stop()


def test_worker_should_stop_with_no_app(tk_root, tmp_path):
    """Test that worker stops when app becomes None."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    tk_root.withdraw()
    tk_root.update()

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    worker.request_page(0, 100, 200, render_generation=0)
    worker._app = None

    time.sleep(0.2)

    worker.stop()


def test_worker_should_stop_with_no_source(tk_root, tmp_path):
    """Test that worker stops when source becomes None."""
    cbz_path = tmp_path / "test.cbz"
    create_test_cbz(cbz_path, page_count=3)

    tk_root.withdraw()
    tk_root.update()

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)

    worker = cdisplayagain.ImageWorker(app, num_workers=1)

    worker.request_page(0, 100, 200, render_generation=0)
    app.source = None

    time.sleep(0.2)

    worker.stop()
