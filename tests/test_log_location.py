"""Tests for choosing a writable log directory across launch contexts."""

import sys
from pathlib import Path

import pytest

import cdisplayagain


@pytest.fixture(autouse=True)
def restore_log_state():
    """Keep log-root mutations from leaking into other tests."""
    original_root = cdisplayagain.LOG_ROOT
    original_path = cdisplayagain.LOG_PATH
    yield
    cdisplayagain.LOG_ROOT = original_root
    cdisplayagain.LOG_PATH = original_path


def test_default_log_root_prefers_env_override(monkeypatch, tmp_path):
    """An explicit CDISPLAYAGAIN_LOG_DIR wins over every platform default."""
    monkeypatch.setenv("CDISPLAYAGAIN_LOG_DIR", str(tmp_path / "custom"))

    assert cdisplayagain._default_log_root() == tmp_path / "custom"


def test_default_log_root_is_relative_for_source_runs(monkeypatch):
    """A source checkout keeps logging beside the working directory."""
    monkeypatch.delenv("CDISPLAYAGAIN_LOG_DIR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert cdisplayagain._default_log_root() == Path("logs")


def test_default_log_root_is_user_scoped_when_frozen(monkeypatch):
    """A packaged app logs under the user's directory, not the launch directory.

    Finder starts a bundled app in "/", so a relative log path aborts startup.
    """
    monkeypatch.delenv("CDISPLAYAGAIN_LOG_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    root = cdisplayagain._default_log_root()

    assert root.is_absolute()
    assert root == cdisplayagain._user_log_root()


def test_user_log_root_uses_library_logs_on_macos(monkeypatch):
    """Keep application logs in ~/Library/Logs on macOS."""
    monkeypatch.setattr(sys, "platform", "darwin")

    assert cdisplayagain._user_log_root() == Path.home() / "Library" / "Logs" / "cdisplayagain"


def test_user_log_root_honors_xdg_state_home(monkeypatch, tmp_path):
    """Linux follows XDG_STATE_HOME when it is set."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert cdisplayagain._user_log_root() == tmp_path / "cdisplayagain" / "logs"


def test_init_logging_writes_under_configured_root(monkeypatch, tmp_path):
    """The configured root is used when it is writable."""
    monkeypatch.setattr(cdisplayagain, "LOG_ROOT", tmp_path)

    cdisplayagain._init_logging()

    assert cdisplayagain.LOG_PATH is not None
    assert tmp_path in cdisplayagain.LOG_PATH.parents


def test_init_logging_falls_back_when_root_is_unwritable(monkeypatch, tmp_path):
    """An unwritable root falls back to the per-user location instead of crashing."""
    fallback = tmp_path / "fallback"
    monkeypatch.setattr(cdisplayagain, "LOG_ROOT", Path("/proc/nonexistent/logs"))
    monkeypatch.setattr(cdisplayagain, "_user_log_root", lambda: fallback)

    cdisplayagain._init_logging()

    assert cdisplayagain.LOG_PATH is not None
    assert fallback in cdisplayagain.LOG_PATH.parents


def test_init_logging_survives_with_no_writable_directory(monkeypatch):
    """No writable directory anywhere disables file logging rather than aborting."""

    def _refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", _refuse)

    cdisplayagain._init_logging()

    assert cdisplayagain.LOG_PATH is None
