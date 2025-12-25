"""Test cleanup error logging in load functions."""

import io
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import cdisplayagain


def _write_image(path: Path, size=(80, 120), color=(255, 0, 0)) -> None:
    img = Image.new("RGB", size, color=color)
    img.save(path)


def _make_cbz(path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            buf = io.BytesIO()
            img = Image.new("RGB", (64, 64), color=(10, 20, 30))
            img.save(buf, format="PNG")
            zf.writestr(name, buf.getvalue())


def test_load_cbz_cleanup_logs_error_on_failure(tmp_path, caplog):
    """Verify load_cbz cleanup logs warning when close fails."""
    cbz_path = tmp_path / "test.cbz"
    _make_cbz(cbz_path, ["page1.png"])

    source = cdisplayagain.load_cbz(cbz_path)
    assert source is not None
    assert source.cleanup is not None

    with patch("zipfile.ZipFile.close", side_effect=RuntimeError("Zip file error")):
        with caplog.at_level("WARNING"):
            source.cleanup()
            assert len(caplog.records) == 1
            assert "Cleanup failed" in caplog.text
            assert "Zip file error" in caplog.text


def test_load_tar_cleanup_logs_error_on_failure(tmp_path, caplog):
    """Verify load_tar cleanup logs warning when close fails."""
    tar_path = tmp_path / "test.tar"
    with tarfile.open(tar_path, "w") as tf:
        buf = io.BytesIO()
        img = Image.new("RGB", (64, 64), color=(10, 20, 30))
        img.save(buf, format="PNG")
        data = buf.getvalue()
        info = tarfile.TarInfo("page1.png")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)
    assert source is not None
    assert source.cleanup is not None

    with patch("tarfile.TarFile.close", side_effect=RuntimeError("Tar file error")):
        with caplog.at_level("WARNING"):
            source.cleanup()
            assert len(caplog.records) == 1
            assert "Cleanup failed" in caplog.text
            assert "Tar file error" in caplog.text


def test_cleanup_logging_in_open_comic(tmp_path, caplog):
    """Verify _open_comic logs warning when cleanup fails."""
    cbz_path = tmp_path / "test.cbz"
    _make_cbz(cbz_path, ["page1.png"])

    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    root.attributes("-alpha", 0.0)

    try:
        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        assert viewer.source is not None
        assert viewer.source.cleanup is not None

        def failing_cleanup():
            raise RuntimeError("Cleanup error")

        viewer.source.cleanup = failing_cleanup

        cbz_path2 = tmp_path / "test2.cbz"
        _make_cbz(cbz_path2, ["page2.png"])

        with caplog.at_level("WARNING"):
            viewer._open_comic(cbz_path2)
            assert len(caplog.records) == 1
            assert "Cleanup failed" in caplog.text
            assert "Cleanup error" in caplog.text
    finally:
        root.destroy()


def test_cleanup_success_no_logging(tmp_path, caplog):
    """Verify cleanup doesn't log when it succeeds."""
    cbz_path = tmp_path / "test.cbz"
    _make_cbz(cbz_path, ["page1.png"])

    source = cdisplayagain.load_cbz(cbz_path)
    assert source is not None
    assert source.cleanup is not None

    with caplog.at_level("WARNING"):
        source.cleanup()
        assert len(caplog.records) == 0
