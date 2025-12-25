"""Extra coverage for error paths and helpers."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_natural_key_orders_numeric_segments():
    """Ensure natural sort keys order numeric segments as expected."""
    assert cdisplayagain.natural_key("10.png") > cdisplayagain.natural_key("2.png")


def test_is_image_and_text_name():
    """Verify helper checks for image and text suffixes."""
    assert cdisplayagain.is_image_name("page.PNG") is True
    assert cdisplayagain.is_text_name("info.NFO") is True
    assert cdisplayagain.is_image_name("notes.txt") is False


def test_load_directory_rejects_non_directory(tmp_path):
    """Reject load attempts for missing directories."""
    bad_path = tmp_path / "missing"
    with pytest.raises(RuntimeError, match="not a directory"):
        cdisplayagain.load_directory(bad_path)


def test_load_directory_rejects_empty_directory(tmp_path):
    """Reject empty directories without any pages."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="No images"):
        cdisplayagain.load_directory(empty)


def test_load_image_file_rejects_non_image(tmp_path):
    """Reject non-image file paths when loading single pages."""
    text_path = tmp_path / "readme.txt"
    text_path.write_text("hi")
    with pytest.raises(RuntimeError, match="Not an image"):
        cdisplayagain.load_image_file(text_path)


def test_load_cbz_rejects_empty_archive(tmp_path):
    """Reject empty CBZ files without any pages."""
    cbz_path = tmp_path / "empty.cbz"
    with zipfile.ZipFile(cbz_path, "w"):
        pass
    with pytest.raises(RuntimeError, match="No images"):
        cdisplayagain.load_cbz(cbz_path)


def test_load_cbz_cleanup_handles_close_failure(tmp_path, monkeypatch):
    """Ignore cleanup errors when closing CBZ handles."""
    cbz_path = tmp_path / "comic.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("01.png", b"fake")

    original_close = zipfile.ZipFile.close

    def fail_close(self):
        raise RuntimeError("boom")

    source = cdisplayagain.load_cbz(cbz_path)
    monkeypatch.setattr(zipfile.ZipFile, "close", fail_close)
    source.cleanup()
    monkeypatch.setattr(zipfile.ZipFile, "close", original_close)


def test_load_tar_rejects_empty_archive(tmp_path):
    """Reject empty TAR files without any pages."""
    tar_path = tmp_path / "empty.tar"
    with tarfile.open(tar_path, "w"):
        pass
    with pytest.raises(RuntimeError, match="No images"):
        cdisplayagain.load_tar(tar_path)


def test_load_tar_missing_member_raises(tmp_path):
    """Raise when requested TAR members are missing."""
    tar_path = tmp_path / "comic.tar"
    with tarfile.open(tar_path, "w") as tf:
        data = b"data"
        info = tarfile.TarInfo("01.png")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)
    with pytest.raises(RuntimeError, match="Missing entry"):
        source.get_bytes("missing.png")


def test_load_tar_extractfile_none_raises(tmp_path, monkeypatch):
    """Raise when TAR members cannot be extracted."""
    tar_path = tmp_path / "comic.tar"
    with tarfile.open(tar_path, "w") as tf:
        data = b"data"
        info = tarfile.TarInfo("01.png")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)

    def fake_extractfile(self, member):
        return None

    monkeypatch.setattr(tarfile.TarFile, "extractfile", fake_extractfile)
    with pytest.raises(RuntimeError, match="Could not read TAR member"):
        source.get_bytes("01.png")


def test_load_comic_unsupported_extension(tmp_path):
    """Reject unsupported file types."""
    bad_path = tmp_path / "comic.xyz"
    bad_path.write_text("nope")
    with pytest.raises(RuntimeError, match="Unsupported type"):
        cdisplayagain.load_comic(bad_path)


def test_load_comic_empty_tar_returns_placeholder(tmp_path):
    """Return a placeholder page for empty TAR files."""
    tar_path = tmp_path / "empty.tar"
    tar_path.write_bytes(b"")
    source = cdisplayagain.load_comic(tar_path)
    assert source.pages == ["01.png"]


def test_load_comic_empty_cbr_returns_placeholder(tmp_path):
    """Return a placeholder page for empty CBR files."""
    cbr_path = tmp_path / "empty.cbr"
    cbr_path.write_bytes(b"")
    source = cdisplayagain.load_comic(cbr_path)
    assert source.pages == ["01.png"]


def test_load_cbr_requires_unar(monkeypatch, tmp_path):
    """Require unar for CBR extraction."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"data")
    monkeypatch.setattr(cdisplayagain.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="requires 'unar'"):
        cdisplayagain.load_cbr(cbr_path)


def test_load_comic_dispatches_image(tmp_path):
    """Dispatch image files through the image loader."""
    img_path = tmp_path / "page.png"
    _write_image(img_path)
    source = cdisplayagain.load_comic(img_path)
    assert source.pages == ["page.png"]


def test_load_cbr_unar_subprocess_failure(tmp_path, monkeypatch):
    """Raise when unar subprocess fails."""
    cbr_path = tmp_path / "comic.cbr"

    def fake_run(*args, **kwargs):
        return type("FakeResult", (), {"returncode": 1, "stderr": "error", "stdout": ""})()

    monkeypatch.setattr(cdisplayagain.subprocess, "run", fake_run)
    monkeypatch.setattr(cdisplayagain.shutil, "which", lambda _: "/usr/bin/unar")
    with pytest.raises(RuntimeError, match="unar failed"):
        cdisplayagain.load_cbr(cbr_path)


def test_load_directory_text_file(tmp_path):
    """Load directory with text and image files."""
    (tmp_path / "readme.txt").write_text("info")
    (tmp_path / "page01.png").write_bytes(b"png")
    (tmp_path / "page02.jpg").write_bytes(b"jpg")

    source = cdisplayagain.load_directory(tmp_path)
    assert "readme.txt" in source.pages
    assert "page01.png" in source.pages
    assert "page02.jpg" in source.pages


def test_load_cbz_mixed_content(tmp_path):
    """Load CBZ with mixed text and image files."""
    cbz_path = tmp_path / "mixed.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("readme.nfo", b"info")
        zf.writestr("page1.jpg", b"image1")
        zf.writestr("page2.png", b"image2")
        zf.writestr("page3.jpg", b"image3")

    source = cdisplayagain.load_cbz(cbz_path)
    assert source.pages[0] == "readme.nfo"
    assert "page1.jpg" in source.pages
    assert "page2.png" in source.pages
    assert "page3.jpg" in source.pages


def test_load_tar_mixed_content(tmp_path):
    """Load TAR with mixed text and image files."""
    tar_path = tmp_path / "mixed.tar"
    with tarfile.open(tar_path, "w") as tf:
        data = b"data"
        info1 = tarfile.TarInfo("readme.nfo")
        info1.size = len(data)
        tf.addfile(info1, io.BytesIO(data))

        info2 = tarfile.TarInfo("page1.jpg")
        info2.size = len(data)
        tf.addfile(info2, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)
    assert "readme.nfo" in source.pages
    assert "page1.jpg" in source.pages


def test_natural_key_various_formats():
    """Test natural key with various number formats."""
    tests = [
        ("page-1.png", "page-2.png"),
        ("page-2.png", "page-10.png"),
        ("page-001.png", "page-010.png"),
        ("chapter1page2.jpg", "chapter1page10.jpg"),
    ]
    for first, second in tests:
        assert cdisplayagain.natural_key(first) < cdisplayagain.natural_key(second), (
            f"{first} should be before {second}"
        )


def test_require_unar_missing_unar(monkeypatch):
    """Raise SystemExit when unar is not available."""
    monkeypatch.setattr(cdisplayagain.shutil, "which", lambda _: None)
    with pytest.raises(SystemExit, match="CBR support requires"):
        cdisplayagain.require_unar()


def test_require_unar_available(monkeypatch):
    """Return early when unar is available."""
    monkeypatch.setattr(cdisplayagain.shutil, "which", lambda _: "/usr/bin/unar")
    cdisplayagain.require_unar()
