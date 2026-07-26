"""FocusRestorer scheduling behavior tests."""

import tkinter as tk
from pathlib import Path
from typing import cast

from PIL import Image

from cdisplayagain import ComicViewer, FocusRestorer


def _write_image(path: Path) -> None:
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(path)


def test_focus_restorer_schedules_once_until_run():
    """Schedule only one idle callback until the callback runs."""
    scheduled_callbacks = []
    focused = []

    def fake_after_idle(callback):
        scheduled_callbacks.append(callback)

    def fake_focus():
        focused.append(True)

    restorer = FocusRestorer(fake_after_idle, fake_focus)

    restorer.schedule()
    restorer.schedule()

    assert len(scheduled_callbacks) == 1

    scheduled_callbacks[0]()

    assert focused == [True]

    restorer.schedule()

    assert len(scheduled_callbacks) == 2


def test_focus_restorer_cancel_clears_pending_callback():
    """Canceling focus restoration prevents the queued callback from focusing."""
    scheduled_callbacks = []
    canceled_ids = []
    focused = []

    def fake_after_idle(callback):
        scheduled_callbacks.append(callback)
        return f"job-{len(scheduled_callbacks)}"

    def fake_after_cancel(job_id):
        canceled_ids.append(job_id)

    restorer = FocusRestorer(fake_after_idle, lambda: focused.append(True), fake_after_cancel)

    restorer.schedule()
    restorer.cancel()
    scheduled_callbacks[0]()

    assert canceled_ids == ["job-1"]
    assert focused == []


def test_focus_restorer_cancel_without_pending_is_noop():
    """Canceling without a queued callback does nothing."""
    restorer = FocusRestorer(lambda callback: "unused", lambda: None)

    restorer.cancel()

    assert restorer._pending is False


def test_focus_restorer_repeated_schedule_after_cancel_is_bounded():
    """Repeated scheduling still leaves at most one active callback."""
    scheduled_callbacks = []

    def fake_after_idle(callback):
        scheduled_callbacks.append(callback)
        return f"job-{len(scheduled_callbacks)}"

    restorer = FocusRestorer(fake_after_idle, lambda: None)

    for _ in range(20):
        restorer.schedule()

    assert len(scheduled_callbacks) == 1


def test_focus_in_cancels_without_scheduling():
    """FocusIn only clears pending restoration and never requests another one."""
    calls = []

    class FakeFocusRestorer:
        def cancel(self):
            calls.append("cancel")

        def schedule(self):
            calls.append("schedule")

    viewer = type("Viewer", (), {"_focus_restorer": FakeFocusRestorer()})()

    for _ in range(20):
        ComicViewer._on_focus_in(cast(ComicViewer, viewer), cast(tk.Event, None))

    assert calls == ["cancel"] * 20


def test_focus_out_schedules_at_most_one_callback():
    """Repeated FocusOut events use FocusRestorer's one-callback guard."""
    scheduled_callbacks = []

    def fake_after_idle(callback):
        scheduled_callbacks.append(callback)
        return f"job-{len(scheduled_callbacks)}"

    restorer = FocusRestorer(fake_after_idle, lambda: None)
    viewer = type(
        "Viewer",
        (),
        {
            "_focus_restorer": restorer,
            "_request_focus": lambda self: self._focus_restorer.schedule(),
        },
    )()

    for _ in range(20):
        ComicViewer._on_focus_out(cast(ComicViewer, viewer), cast(tk.Event, None))

    assert len(scheduled_callbacks) == 1


def test_ensure_focus_ignores_canvas_tcl_error(tk_root, tmp_path, monkeypatch):
    """A destroyed canvas cannot make focus restoration fail the UI."""
    image_path = tmp_path / "page.png"
    _write_image(image_path)
    viewer = ComicViewer(tk_root, image_path)

    def fail_focus_set():
        raise tk.TclError("canvas unavailable")

    monkeypatch.setattr(viewer.canvas, "focus_set", fail_focus_set)

    viewer._ensure_focus()
