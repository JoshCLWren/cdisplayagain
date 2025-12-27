"""Test error handling paths that need additional coverage."""

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

import cdisplayagain


def _make_cbz(path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            buf = io.BytesIO()
            img = Image.new("RGB", (64, 64), color=(10, 20, 30))
            img.save(buf, format="PNG")
            zf.writestr(name, buf.getvalue())


def _make_dummy_cbr(tmp_path: Path) -> Path:
    """Create a minimal dummy CBR file for testing."""
    cbr_path = tmp_path / "test.cbr"
    cbr_path.write_bytes(b"dummy rar content")
    return cbr_path


def test_cbr_exception_cleanup_logging(tmp_path, caplog):
    """Verify CBR cleanup logs warning when exception occurs during cleanup."""
    cbr_path = _make_dummy_cbr(tmp_path)

    with patch("shutil.rmtree", side_effect=RuntimeError("Directory access error")):
        with caplog.at_level("WARNING"):
            cdisplayagain.load_cbr(cbr_path)
            assert len(caplog.records) >= 1
            assert any("CBR cleanup failed" in record.message for record in caplog.records)


def test_tar_exception_cleanup_logging(tmp_path, caplog):
    """Verify TAR cleanup logs warning when exception occurs during cleanup."""
    tar_path = tmp_path / "test.tar"
    tar_path.write_bytes(b"invalid tar content")

    with patch("tarfile.open", side_effect=RuntimeError("Tar error")):
        with caplog.at_level("WARNING"):
            with pytest.raises(RuntimeError):
                cdisplayagain.load_tar(tar_path)


def test_dialog_cancellation_no_exceptions(tk_root, tmp_path):
    """Verify _cancel_active_dialog runs without exceptions."""
    cbz_path = tmp_path / "test.cbz"
    _make_cbz(cbz_path, ["page1.png"])
    viewer = cdisplayagain.ComicViewer(tk_root, cbz_path)
    viewer._cancel_active_dialog()
