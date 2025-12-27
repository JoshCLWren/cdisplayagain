"""Tests for cursor operations and TclError handling."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_configure_cursor_tclerror_fallback(tk_root, tmp_path, monkeypatch):
    """Test _configure_cursor handles TclError by trying alternative cursors."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    call_count = [0]

    def failing_configure(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:
            raise tk.TclError("Invalid cursor name")
        return original_configure(*args, **kwargs)

    original_configure = viewer.configure
    monkeypatch.setattr(viewer, "configure", failing_configure)

    viewer._configure_cursor()
    assert call_count[0] == 3


def test_configure_cursor_all_cursors_fail(tk_root, tmp_path, monkeypatch):
    """Test _configure_cursor handles all cursor options failing."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    original_cursor_name = viewer._cursor_name

    def always_failing_configure(*args, **kwargs):
        raise tk.TclError("Invalid cursor name")

    monkeypatch.setattr(viewer, "configure", always_failing_configure)

    viewer._configure_cursor()
    assert viewer._cursor_name == original_cursor_name


def test_set_cursor_hidden_true_tclerror(tk_root, tmp_path, monkeypatch):
    """Test _set_cursor_hidden handles TclError when hiding cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_name = "arrow"

    call_count = [0]

    def failing_configure(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise tk.TclError("none cursor not supported")
        return original_configure(*args, **kwargs)

    original_configure = viewer.configure
    monkeypatch.setattr(viewer, "configure", failing_configure)

    viewer._set_cursor_hidden(True)
    assert call_count[0] == 2
    assert viewer._cursor_hidden is True


def test_set_cursor_hidden_true_tclerror_canvas_also_fails(tk_root, tmp_path, monkeypatch):
    """Test _set_cursor_hidden handles TclError from both widgets."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_name = "arrow"

    call_count = [0]

    def failing_configure(*args, **kwargs):
        call_count[0] += 1
        raise tk.TclError("Cursor not supported")

    monkeypatch.setattr(viewer, "configure", failing_configure)
    monkeypatch.setattr(viewer.canvas, "configure", failing_configure)

    viewer._set_cursor_hidden(True)
    assert viewer._cursor_hidden is True


def test_set_cursor_hidden_false_tclerror(tk_root, tmp_path, monkeypatch):
    """Test _set_cursor_hidden handles TclError when showing cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_name = "arrow"
    viewer._cursor_hidden = True

    def failing_configure(*args, **kwargs):
        raise tk.TclError("Invalid cursor")

    monkeypatch.setattr(viewer, "configure", failing_configure)
    monkeypatch.setattr(viewer.canvas, "configure", failing_configure)

    viewer._set_cursor_hidden(False)
    assert viewer._cursor_hidden is False


def test_ensure_focus_tclerror(tk_root, tmp_path, monkeypatch):
    """Test _ensure_focus handles TclError gracefully."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    def failing_focus_force():
        raise tk.TclError("Cannot focus")

    monkeypatch.setattr(viewer, "focus_force", failing_focus_force)

    viewer._ensure_focus()
    assert True


def test_toggle_fullscreen_tclerror_on_check(tk_root, tmp_path, monkeypatch):
    """Test toggle_fullscreen handles exception when checking fullscreen state."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    class FakeWM:
        def attributes(self, *args, **kwargs):
            raise tk.TclError("Cannot get attributes")

    monkeypatch.setattr(cdisplayagain, "_as_wm", lambda x: FakeWM())

    viewer._fullscreen = False
    viewer.toggle_fullscreen()
    assert viewer._fullscreen is True


def test_toggle_fullscreen_tclerror_on_set(tk_root, tmp_path, monkeypatch):
    """Test toggle_fullscreen handles TclError when setting fullscreen."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    class FakeWM:
        def __init__(self):
            self._full = False

        def attributes(self, *args, **kwargs):
            if len(args) == 1:
                return "0" if not self._full else "1"
            else:
                raise tk.TclError("Cannot set fullscreen")

    monkeypatch.setattr(cdisplayagain, "_as_wm", lambda x: FakeWM())

    viewer.toggle_fullscreen()
    assert viewer._fullscreen is True


def test_set_cursor_hidden_show_after_hidden(tk_root, tmp_path, monkeypatch):
    """Test _set_cursor_hidden transitions from hidden to shown."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_name = "arrow"
    viewer._cursor_hidden = True

    viewer._set_cursor_hidden(False)
    assert viewer._cursor_hidden is False


def test_set_cursor_hidden_no_cursor_name(tk_root, tmp_path, monkeypatch):
    """Test _set_cursor_hidden when configure fails for all cursor names."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    def failing_configure(*args, **kwargs):
        raise tk.TclError("Invalid cursor")

    monkeypatch.setattr(viewer, "configure", failing_configure)
    monkeypatch.setattr(viewer.canvas, "configure", failing_configure)

    viewer._set_cursor_hidden(True)
    assert viewer._cursor_hidden is True


def test_ensure_focus_calls_canvas_focus_set(tk_root, tmp_path, monkeypatch):
    """Test _ensure_focus calls canvas.focus_set regardless of focus_force result."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    focus_set_called = [False]

    def tracking_focus_set():
        focus_set_called[0] = True

    monkeypatch.setattr(viewer.canvas, "focus_set", tracking_focus_set)

    viewer._ensure_focus()
    assert focus_set_called[0] is True


def test_configure_cursor_sets_first_successful(tk_root, tmp_path):
    """Test _configure_cursor sets first successful cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    viewer._configure_cursor()
    assert viewer._cursor_name in ("none", "dotbox", "arrow")


def test_set_cursor_hidden_true_normal_case(tk_root, tmp_path):
    """Test _set_cursor_hidden successfully hides cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_hidden = False

    viewer._set_cursor_hidden(True)
    assert viewer._cursor_hidden is True


def test_set_cursor_hidden_false_normal_case(tk_root, tmp_path):
    """Test _set_cursor_hidden successfully shows cursor."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._cursor_hidden = True

    viewer._set_cursor_hidden(False)
    assert viewer._cursor_hidden is False


def test_prime_imagetk_already_ready(tk_root, tmp_path):
    """Test _prime_imagetk returns early when already ready."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._imagetk_ready = True

    viewer._prime_imagetk()
    assert viewer._imagetk_ready is True


def test_prime_imagetk_tkapp_no_interpaddr_attr(tk_root, tmp_path, monkeypatch):
    """Test _prime_imagetk when tkapp has no interpaddr attribute."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._imagetk_ready = False

    class FakeTkapp:
        pass

    original_tk = viewer.tk
    monkeypatch.setattr(viewer, "tk", FakeTkapp())

    viewer._prime_imagetk()
    assert viewer._imagetk_ready is False

    monkeypatch.setattr(viewer, "tk", original_tk)


def test_prime_imagetk_tkapp_none(tk_root, tmp_path, monkeypatch):
    """Test _prime_imagetk when tk attribute is None."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._imagetk_ready = False

    original_tk = viewer.tk
    monkeypatch.setattr(viewer, "tk", None)

    viewer._prime_imagetk()
    assert viewer._imagetk_ready is False

    monkeypatch.setattr(viewer, "tk", original_tk)
