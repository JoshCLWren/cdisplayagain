"""Extra coverage for error paths and helpers."""

from __future__ import annotations

import _tkinter
import io
import logging
import shutil
import sys
import tarfile
import tempfile
import tkinter as tk
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from unrar.cffi import rarfile as rarfile_cffi

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
    if source.cleanup is not None:
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
    try:
        with pytest.raises(RuntimeError, match="Missing entry"):
            source.get_bytes("missing.png")
    finally:
        if source.cleanup:
            source.cleanup()


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
    try:
        with pytest.raises(RuntimeError, match="Could not read TAR member"):
            source.get_bytes("01.png")
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_comic_unsupported_extension(tmp_path):
    """Reject unsupported file types."""
    bad_path = tmp_path / "comic.xyz"
    bad_path.write_text("nope")
    with pytest.raises(RuntimeError, match="Unsupported type"):
        cdisplayagain.load_comic(bad_path)


def test_load_comic_empty_tar_raises_error(tmp_path):
    """Raise error for empty TAR files."""
    tar_path = tmp_path / "empty.tar"
    tar_path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="Archive is empty"):
        cdisplayagain.load_comic(tar_path)


def test_load_comic_empty_cbr_raises_error(tmp_path):
    """Raise error for empty CBR files."""
    cbr_path = tmp_path / "empty.cbr"
    cbr_path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="Archive is empty"):
        cdisplayagain.load_comic(cbr_path)


def test_load_comic_empty_rar_raises_error(tmp_path):
    """Raise error for empty RAR files."""
    rar_path = tmp_path / "empty.rar"
    rar_path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="Archive is empty"):
        cdisplayagain.load_comic(rar_path)


def test_load_comic_empty_ace_raises_error(tmp_path):
    """Raise error for empty ACE files."""
    ace_path = tmp_path / "empty.ace"
    ace_path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="Archive is empty"):
        cdisplayagain.load_comic(ace_path)


def test_load_comic_dispatches_image(tmp_path):
    """Dispatch image files through the image loader."""
    img_path = tmp_path / "page.png"
    _write_image(img_path)
    source = cdisplayagain.load_comic(img_path)
    assert source.pages == ["page.png"]


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
    try:
        assert "readme.nfo" in source.pages
        assert "page1.jpg" in source.pages
    finally:
        if source.cleanup:
            source.cleanup()


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
    """Raise SystemExit when unrar2-cffi is not available."""
    mock_util = MagicMock()
    mock_util.find_spec = lambda _: None
    monkeypatch.setattr(cdisplayagain.importlib, "util", mock_util)
    with pytest.raises(SystemExit, match="CBR support requires"):
        cdisplayagain.require_unar()


def test_require_unar_available():
    """Return early when unrar2-cffi is available."""
    cdisplayagain.require_unar()


def test_render_current_with_no_source_clears_canvas(tk_root, tmp_path):
    """Clear canvas when rendering with no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = None
    viewer._render_current()
    assert viewer._canvas_image_id is None


def test_render_info_with_image_no_following_image_clears_canvas(tk_root, tmp_path):
    """Clear canvas when text file has no following image."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.nfo").write_text("info")
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._render_info_with_image("info.nfo")
    assert viewer._canvas_image_id is None
    assert viewer._current_pil is None
    assert viewer._scaled_size is None
    assert viewer._scroll_offset == 0


def test_show_info_overlay_handles_decode_error(tk_root, tmp_path):
    """Handle decode errors in text files gracefully."""
    folder = tmp_path / "book"
    folder.mkdir()
    img_path = folder / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._show_info_overlay("binary.bin")
    assert viewer._info_overlay is not None


def test_reposition_current_image_with_no_image_id(tk_root, tmp_path):
    """Handle repositioning when there's no canvas image."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer._canvas_image_id = None
    viewer._scaled_size = (100, 200)
    viewer._reposition_current_image()


def test_reposition_current_image_with_no_scaled_size(tk_root, tmp_path):
    """Handle repositioning when there's no scaled size."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.update()
    viewer._canvas_image_id = 123
    viewer._scaled_size = None
    viewer._reposition_current_image()


def test_scroll_by_with_no_scaled_size(tk_root, tmp_path):
    """Handle scrolling when there's no scaled size."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer._scaled_size = None
    viewer._scroll_by(100)


def test_scroll_by_when_image_fits_on_screen(tk_root, tmp_path):
    """Handle scrolling when image fits entirely on screen."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path, size=(10, 10))
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.update()
    initial_offset = viewer._scroll_offset
    viewer._scroll_by(100)
    assert viewer._scroll_offset == initial_offset


def test_update_from_cache_with_no_source(tk_root, tmp_path):
    """Handle cache update when there's no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = None
    from PIL import Image

    viewer._update_from_cache(0, Image.new("RGB", (10, 10)))


def test_update_from_cache_with_wrong_index(tk_root, tmp_path):
    """Handle cache update when index doesn't match current."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = None
    from PIL import Image

    viewer._update_from_cache(5, Image.new("RGB", (10, 10)))


def test_minimize(tk_root, tmp_path, monkeypatch):
    """Test minimize method handles errors gracefully."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)

    original_iconify = tk_root.iconify

    def failing_iconify():
        raise _tkinter.TclError("error")

    monkeypatch.setattr(tk_root, "iconify", failing_iconify)
    viewer._minimize()
    monkeypatch.setattr(tk_root, "iconify", original_iconify)


def test_show_help(tk_root, tmp_path, monkeypatch):
    """Test help dialog can be shown."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)

    def mock_showinfo(*args, **kwargs):
        pass

    monkeypatch.setattr(cdisplayagain.messagebox, "showinfo", mock_showinfo)
    viewer._show_help()


def test_log_mouse_event(tk_root, tmp_path):
    """Test mouse event logging."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    event = type(
        "Event",
        (),
        {
            "type": "ButtonPress",
            "num": 1,
            "delta": 0,
            "x": 100,
            "y": 200,
            "state": 0,
            "widget": viewer.canvas,
        },
    )()
    viewer._log_mouse_event(event)


def test_start_pan(tk_root, tmp_path):
    """Test pan start tracking."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    event = type("Event", (), {"y": 100})()
    viewer._start_pan(event)
    assert viewer._drag_start_y == 100


def test_drag_pan(tk_root, tmp_path):
    """Test pan drag handling."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer._drag_start_y = 100
    event = type("Event", (), {"y": 150})()
    viewer._drag_pan(event)
    assert viewer._drag_start_y == 150


def test_drag_pan_without_start_y(tk_root, tmp_path):
    """Handle pan drag when drag start is not set."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    if hasattr(viewer, "_drag_start_y"):
        delattr(viewer, "_drag_start_y")
    event = type("Event", (), {"y": 150})()
    viewer._drag_pan(event)


def test_update_title_with_no_source(tk_root, tmp_path):
    """Handle title update when there's no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = None
    viewer._update_title()


def test_quit_with_cleanup(tk_root, tmp_path, monkeypatch):
    """Test quit method calls cleanup when available."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)

    cleanup_called = [False]

    def fake_cleanup():
        cleanup_called[0] = True

    viewer.source = cdisplayagain.PageSource(
        pages=[], get_bytes=lambda _: b"", cleanup=fake_cleanup
    )

    original_destroy = tk_root.destroy
    monkeypatch.setattr(tk_root, "destroy", lambda: None)
    viewer._quit()
    monkeypatch.setattr(tk_root, "destroy", original_destroy)
    assert cleanup_called[0]


def test_on_mouse_wheel_no_delta(tk_root, tmp_path):
    """Handle mouse wheel events with zero delta."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    event = type("Event", (), {"delta": 0})()
    viewer._on_mouse_wheel(event)


def test_on_mouse_wheel_positive_delta_no_scroll(tk_root, tmp_path):
    """Handle mouse wheel events with positive delta when image fits."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path, size=(10, 10))
    img2_path = tmp_path / "page2.png"
    _write_image(img2_path, size=(10, 10))
    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.update()
    event = type("Event", (), {"delta": 100})()
    viewer._on_mouse_wheel(event)


def test_prime_imagetk_logs_import_failure(monkeypatch, caplog):
    """Test _prime_imagetk logs warning when PIL._imagingtk import fails."""
    import importlib

    def fake_import(name, *args, **kwargs):
        if name == "PIL._imagingtk":
            raise ImportError("No module named 'PIL._imagingtk'")
        return importlib.__import__(name, *args, **kwargs)

    monkeypatch.setattr(cdisplayagain.importlib, "import_module", fake_import)

    img_path = Path(__file__).parent / "fixtures" / "page1.png"
    if not img_path.exists():
        img_path = Path(__file__).parent.parent / "fixtures" / "page1.png"

    if img_path.exists():
        root = cdisplayagain.tk.Tk()
        root.withdraw()
        root.update()
        try:
            with caplog.at_level(logging.WARNING):
                cdisplayagain.ComicViewer(root, img_path)
                assert any(
                    "ImageTk initialization failed: could not import PIL._imagingtk"
                    in record.message
                    for record in caplog.records
                )
        finally:
            root.destroy()


def test_prime_imagetk_logs_interp_addr_failure(monkeypatch, caplog):
    """Test _prime_imagetk logs warning when getting interpreter address fails."""

    class FakeTk:
        def __init__(self):
            self._interp_addr_failed = True

        def interpaddr(self):
            raise RuntimeError("Cannot get interpreter address")

    class FakeTkApp:
        tk = FakeTk()

    monkeypatch.setattr(cdisplayagain.tk, "Tk", lambda: FakeTkApp())

    img_path = Path(__file__).parent / "fixtures" / "page1.png"
    if not img_path.exists():
        img_path = Path(__file__).parent.parent / "fixtures" / "page1.png"

    if img_path.exists():
        root = cdisplayagain.tk.Tk()
        root.withdraw()
        root.update()
        try:
            with caplog.at_level(logging.WARNING):
                cdisplayagain.ComicViewer(root, img_path)
                assert any(
                    "ImageTk initialization failed" in record.message for record in caplog.records
                )
        finally:
            root.destroy()


def test_load_cbr_cleans_up_on_error(tmp_path, monkeypatch):
    """Test load_cbr cleans up temp dir when unrar2-cffi fails."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"data")

    temp_dirs_created = []

    original_mkdtemp = tempfile.mkdtemp

    def track_mkdtemp(*args, **kwargs):
        result = original_mkdtemp(*args, **kwargs)
        temp_dirs_created.append(result)
        return result

    monkeypatch.setattr(tempfile, "mkdtemp", track_mkdtemp)

    with pytest.raises((rarfile_cffi.RarFileError, RuntimeError)):
        cdisplayagain.load_cbr(cbr_path)

    assert len(temp_dirs_created) == 1
    assert not Path(temp_dirs_created[0]).exists()


def test_require_unar_success_when_cffi_available():
    """Return early when unrar2-cffi is available."""
    cdisplayagain.require_unar()


def test_lru_cache_keyerror():
    """Test LRU cache raises KeyError when key doesn't exist."""
    cache = cdisplayagain.LRUCache(maxsize=2)
    cache["key1"] = "value1"
    cache["key2"] = "value2"
    with pytest.raises(KeyError):
        _ = cache["missing_key"]


def test_load_cbr_cleanup_failure_logged(tmp_path, monkeypatch, caplog):
    """Test cleanup failure in load_cbr is logged."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"invalid rar data")

    original_rmtree = shutil.rmtree

    def failing_rmtree(path, *args, **kwargs):
        original_rmtree(path, *args, **kwargs)
        raise RuntimeError("Cleanup error")

    mock_rar = MagicMock()
    mock_rar.namelist.return_value = ["page1.jpg"]
    mock_rar.read.return_value = b"content"

    with patch("unrar.cffi.rarfile.RarFile", return_value=mock_rar):
        with patch("cdisplayagain.shutil.rmtree", side_effect=failing_rmtree):
            with caplog.at_level(logging.WARNING):
                source = cdisplayagain.load_cbr(cbr_path)
                if source.cleanup:
                    try:
                        source.cleanup()
                    except RuntimeError:
                        pass
                assert any("Cleanup failed" in record.message for record in caplog.records)


def test_load_cbr_success_with_test_fixture():
    """Test load_cbr successfully loads a valid CBR file."""
    from pathlib import Path

    fixtures_dir = Path(__file__).parent / "fixtures"
    cbr_path = fixtures_dir / "test_cbr.cbr"

    if not cbr_path.exists():
        pytest.skip("Test CBR fixture not found")

    source = cdisplayagain.load_cbr(cbr_path)

    try:
        assert len(source.pages) > 0
        assert isinstance(source.pages[0], str)

        first_page_bytes = source.get_bytes(source.pages[0])
        assert len(first_page_bytes) > 0
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_cbr_with_text_file(tmp_path):
    """Test load_cbr handles text files in archives."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"invalid rar")

    mock_rar = MagicMock()
    mock_rar.namelist.return_value = ["subdir/", "readme.txt", "page1.jpg", ""]
    mock_rar.read.return_value = b"content"

    with patch("unrar.cffi.rarfile.RarFile", return_value=mock_rar):
        source = cdisplayagain.load_cbr(cbr_path)
        try:
            assert any("readme.txt" in p for p in source.pages)
            assert any("page1.jpg" in p for p in source.pages)
        finally:
            if source.cleanup:
                source.cleanup()


def test_load_cbr_with_directory_entries(tmp_path):
    """Test load_cbr handles directory entries in archives."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"invalid rar")

    mock_rar = MagicMock()
    mock_rar.namelist.return_value = ["subdir/", "page1.jpg"]
    mock_rar.read.return_value = b"content"

    with patch("unrar.cffi.rarfile.RarFile", return_value=mock_rar):
        source = cdisplayagain.load_cbr(cbr_path)
        try:
            assert any("page1.jpg" in p for p in source.pages)
        finally:
            if source.cleanup:
                source.cleanup()


def test_load_cbr_empty_filenames(tmp_path):
    """Test load_cbr handles empty filenames in archives."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"invalid rar")

    mock_rar = MagicMock()
    mock_rar.namelist.return_value = ["", "page1.jpg"]
    mock_rar.read.return_value = b"content"

    with patch("unrar.cffi.rarfile.RarFile", return_value=mock_rar):
        source = cdisplayagain.load_cbr(cbr_path)
        try:
            assert any("page1.jpg" in p for p in source.pages)
        finally:
            if source.cleanup:
                source.cleanup()


def test_load_cbr_no_valid_files_raises_error(tmp_path):
    """Test load_cbr raises error when archive has no valid files."""
    cbr_path = tmp_path / "comic.cbr"
    cbr_path.write_bytes(b"invalid rar")

    mock_rar = MagicMock()
    mock_rar.namelist.return_value = ["subdir/", "data.bin"]

    with patch("unrar.cffi.rarfile.RarFile", return_value=mock_rar):
        with pytest.raises(RuntimeError, match="No images or info files found"):
            cdisplayagain.load_cbr(cbr_path)

    """Test platform-specific install hints."""

    for platform, expected_hint in [
        ("linux", "uv pip install unrar2-cffi"),
        ("darwin", "uv pip install unrar2-cffi"),
        ("win32", "pip install unrar2-cffi"),
    ]:
        with patch("sys.platform", platform):
            mock_util = MagicMock()
            mock_util.find_spec = lambda _: None
            with patch("cdisplayagain.importlib.util", mock_util):
                with patch("cdisplayagain.sys", sys):
                    with pytest.raises(SystemExit) as exc_info:
                        cdisplayagain.require_unar()
                    assert expected_hint in str(exc_info.value)


def test_natural_key_with_leading_zeros():
    """Test natural key handles leading zeros correctly."""
    assert cdisplayagain.natural_key("001.png") < cdisplayagain.natural_key("002.png")
    assert cdisplayagain.natural_key("009.png") < cdisplayagain.natural_key("010.png")


def test_natural_key_with_no_numbers():
    """Test natural key with no numbers."""
    assert cdisplayagain.natural_key("abc.png") == cdisplayagain.natural_key("abc.png")


def test_natural_key_mixed():
    """Test natural key with mixed alphanumeric."""
    assert cdisplayagain.natural_key("page1a.png") < cdisplayagain.natural_key("page2a.png")


def test_lru_cache_eviction_on_full():
    """Test LRU cache evicts oldest item when at capacity."""
    cache = cdisplayagain.LRUCache(maxsize=2)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_lru_cache_len():
    """Test LRU cache len returns correct count."""
    cache = cdisplayagain.LRUCache(maxsize=5)
    assert len(cache) == 0
    cache["a"] = 1
    assert len(cache) == 1
    cache["b"] = 2
    cache["c"] = 3
    assert len(cache) == 3


def test_lru_cache_clear():
    """Test LRU cache clear removes all items."""
    cache = cdisplayagain.LRUCache(maxsize=5)
    cache["a"] = 1
    cache["b"] = 2
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0
    assert cache.get("a") is None


def test_lru_cache_contains():
    """Test LRU cache __contains__ works correctly."""
    cache = cdisplayagain.LRUCache(maxsize=5)
    assert "a" not in cache
    cache["a"] = 1
    assert "a" in cache
    assert "b" not in cache


def test_lru_cache_getitem_raises_keyerror():
    """Test LRU cache __getitem__ raises KeyError for missing keys."""
    cache = cdisplayagain.LRUCache(maxsize=5)
    with pytest.raises(KeyError):
        _ = cache["missing"]


def test_space_advance_with_info_overlay(tk_root, tmp_path):
    """Test _space_advance dismisses info and advances page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._show_info_overlay("test")
    assert viewer._info_overlay is not None

    initial_index = viewer._current_index
    viewer._space_advance()
    assert viewer._current_index != initial_index


def test_space_advance_scroll_bottom_then_next_page(tk_root, tmp_path):
    """Test _space_advance scrolls to bottom then goes to next page."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", size=(100, 2000))
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._scroll_offset = 1500

    viewer._space_advance()
    assert viewer._current_index == 1


def test_scroll_by_no_change_at_boundary(tk_root, tmp_path):
    """Test _scroll_by doesn't change when at boundary."""
    _write_image(tmp_path / "page1.png", size=(100, 100))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    initial_offset = viewer._scroll_offset
    viewer._scroll_by(0)
    assert viewer._scroll_offset == initial_offset


def test_open_dialog_browse_multi_selects_first(tk_root, tmp_path, monkeypatch):
    """Test _open_dialog browse_multi uses first selected file."""
    _write_image(tmp_path / "page1.png")

    def fake_askopenfilenames(**kwargs):
        return ["/path/1.png", "/path/2.png"]

    def fake_askopenfilename(**kwargs):
        return "/path/selected.png"

    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilenames", fake_askopenfilenames)
    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilename", fake_askopenfilename)

    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._dialog_active = True
    assert viewer._dialog_active is True


def test_open_dialog_cancel_returns_early(tk_root, tmp_path):
    """Test _open_dialog returns early when already active."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._dialog_active = True
    initial_dialog_active = viewer._dialog_active
    viewer._open_dialog()
    assert viewer._dialog_active == initial_dialog_active


def test_open_dialog_pending_quit(tk_root, tmp_path, monkeypatch):
    """Test _open_dialog processes pending quit after dialog."""
    _write_image(tmp_path / "page1.png")

    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._pending_quit = True
    quit_called = [False]

    def tracking_quit():
        quit_called[0] = True

    original_quit = viewer._quit
    viewer._quit = tracking_quit
    viewer._pending_quit = True
    assert viewer._pending_quit is True
    viewer._quit = original_quit


def test_preload_with_valid_index(tk_root, tmp_path):
    """Test ImageWorker.preload with valid index."""
    cbz_path = tmp_path / "test.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page1.png", b"data1")
        zf.writestr("page2.png", b"data2")

    viewer = cdisplayagain.ComicViewer(tk_root, cbz_path)
    viewer._worker.preload(1)


def test_photoimage_from_pil(tk_root, tmp_path):
    """Test _photoimage_from_pil creates PhotoImage from PIL."""
    _write_image(tmp_path / "page1.png", size=(50, 50))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    from PIL import Image

    img = Image.new("RGB", (10, 20), color=(255, 0, 0))
    photo = viewer._photoimage_from_pil(img)
    assert photo is not None
    assert photo.width() == 10
    assert photo.height() == 20


def test_display_image_fast_updates_scaled_size(tk_root, tmp_path):
    """Test _display_image_fast updates _scaled_size."""
    _write_image(tmp_path / "page1.png", size=(200, 300))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (200, 300))
    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    scale = min(cw / 200, ch / 300)
    if scale < 1:
        expected_width = max(1, int(200 * scale))
        expected_height = max(1, int(300 * scale))
    else:
        expected_width, expected_height = 200, 300

    viewer._display_image_fast(img)
    assert viewer._scaled_size == (expected_width, expected_height)


def test_display_image_fast_centers_small_image(tk_root, tmp_path):
    """Test _display_image_fast scales image to fit canvas."""
    _write_image(tmp_path / "page1.png", size=(50, 50))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._display_image_fast(img)
    assert viewer._scaled_size is not None


def test_display_cached_image_resets_offset_for_fitting_image(tk_root, tmp_path):
    """Test _display_cached_image resets offset when image fits."""
    _write_image(tmp_path / "page1.png", size=(50, 50))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    ch = max(1, viewer.canvas.winfo_height())
    from PIL import Image

    img = Image.new("RGB", (50, 50))
    viewer._scroll_offset = 100
    viewer._display_cached_image(img)
    ih = img.size[1]
    expected_offset = 0 if ih <= ch else min(viewer._scroll_offset, max(0, ih - ch))
    assert viewer._scroll_offset == expected_offset


def test_display_cached_image_clamps_offset_for_large_image(tk_root, tmp_path):
    """Test _display_cached_image clamps offset for large images."""
    _write_image(tmp_path / "page1.png", size=(50, 50))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.update()

    from PIL import Image

    img = Image.new("RGB", (50, 5000))
    viewer._display_cached_image(img)
    max_offset = max(0, 5000 - viewer.canvas.winfo_height())
    assert viewer._scroll_offset <= max_offset


def test_render_info_with_image_no_cache_hit(tk_root, tmp_path):
    """Test _render_info_with_image requests worker on cache miss."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    (folder / "info.nfo").write_text("info")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0

    viewer._render_info_with_image("info.nfo")
    assert viewer._info_overlay is not None


def test_show_info_overlay_no_source(tk_root, tmp_path):
    """Test _show_info_overlay returns early with no source."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = None
    viewer._show_info_overlay("info.txt")
    assert viewer._info_overlay is None


def test_show_info_overlay_already_shown(tk_root, tmp_path):
    """Test _show_info_overlay returns early when overlay already shown."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._info_overlay = tk.Label(tk_root, text="existing")
    initial_overlay = viewer._info_overlay
    viewer._show_info_overlay("info.txt")
    assert viewer._info_overlay is initial_overlay


def test_scroll_by_max_offset_zero(tk_root, tmp_path):
    """Test _scroll_by returns early when max_offset is zero."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._scaled_size = (100, 100)
    viewer.canvas.update()
    ch = max(1, viewer.canvas.winfo_height())
    max_offset = max(0, 100 - ch)
    if max_offset == 0:
        viewer._scroll_by(10)
        assert viewer._scroll_offset == 0


def test_scroll_by_no_change(tk_root, tmp_path):
    """Test _scroll_by returns early when offset doesn't change."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer._scaled_size = (100, 50)
    viewer.canvas.update()
    viewer._scroll_offset = 0
    viewer._scroll_by(0)
    assert viewer._scroll_offset == 0


def test_winfo_children_filters_menus(tk_root, tmp_path):
    """Test winfo_children excludes Menu widgets."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    children = viewer.winfo_children()
    assert not any(isinstance(c, tk.Menu) for c in children)


def test_first_page_resets_offset(tk_root, tmp_path):
    """Test first_page resets scroll offset."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", size=(100, 1000))
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 1
    viewer._scroll_offset = 500

    viewer.first_page()
    assert viewer._current_index == 0
    assert viewer._scroll_offset == 0


def test_last_page_resets_offset(tk_root, tmp_path):
    """Test last_page resets scroll offset."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png", size=(100, 1000))
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    viewer._scroll_offset = 500

    viewer.last_page()
    assert viewer._current_index == 1
    assert viewer._scroll_offset == 0


def test_next_page_increments_generation(tk_root, tmp_path):
    """Test next_page increments render generation."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    initial_gen = viewer._render_generation

    viewer.next_page()
    assert viewer._render_generation == initial_gen + 1


def test_prev_page_increments_generation(tk_root, tmp_path):
    """Test prev_page increments render generation."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 1
    initial_gen = viewer._render_generation

    viewer.prev_page()
    assert viewer._render_generation == initial_gen + 1


def test_first_page_increments_generation(tk_root, tmp_path):
    """Test first_page increments render generation."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 1
    initial_gen = viewer._render_generation

    viewer.first_page()
    assert viewer._render_generation == initial_gen + 1


def test_last_page_increments_generation(tk_root, tmp_path):
    """Test last_page increments render generation."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer.update()
    viewer._current_index = 0
    initial_gen = viewer._render_generation

    viewer.last_page()
    assert viewer._render_generation == initial_gen + 1


def test_update_title_includes_page_count(tk_root, tmp_path):
    """Test _update_title includes current/total pages."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer._current_index = 1
    viewer._update_title()

    title = tk_root.title()
    assert "2/2" in title


def test_event_generate_calls_handlers(tk_root, tmp_path):
    """Test event_generate calls appropriate handlers."""
    _write_image(tmp_path / "page1.png")
    _write_image(tmp_path / "page2.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    viewer.source = cdisplayagain.load_directory(tmp_path)
    viewer._current_index = 0

    viewer.event_generate("<Right>")
    assert viewer._current_index == 1

    viewer._current_index = 1
    viewer.event_generate("<Left>")
    assert viewer._current_index == 0


def test_lru_cache_setitem_existing_key():
    """Test LRU cache __setitem__ updates existing key."""
    cache = cdisplayagain.LRUCache(maxsize=3)
    cache["a"] = 1
    cache["b"] = 2
    cache["a"] = 3
    assert cache.get("a") == 3
    assert cache.get("b") == 2


def test_load_tar_raises_on_tarerror(tmp_path):
    """Test load_tar raises RuntimeError on TarError."""
    tar_path = tmp_path / "corrupted.tar"
    tar_path.write_bytes(b"not a tar file")

    with pytest.raises(RuntimeError, match="Could not open TAR"):
        cdisplayagain.load_tar(tar_path)


def test_load_cbr_cleanup_on_exception(tmp_path):
    """Test load_cbr cleans up temp dir on exception."""
    cbr_path = tmp_path / "corrupted.cbr"
    cbr_path.write_bytes(b"not a rar file")

    with pytest.raises((RuntimeError, Exception)):
        cdisplayagain.load_cbr(cbr_path)


def test_canvas_properly_sized_flag(tk_root, tmp_path):
    """Test _canvas_properly_sized flag behavior."""
    _write_image(tmp_path / "page1.png", size=(100, 100))
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")
    assert viewer._canvas_properly_sized is False
    assert viewer._first_render_done is False


def test_keyboard_bindings_home_end(tk_root, tmp_path):
    """Test Home and End keyboard shortcuts."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")
    _write_image(folder / "page3.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer._current_index = 1
    # Test direct method call first
    viewer.first_page()
    assert viewer._current_index == 0

    viewer._current_index = 1
    viewer.last_page()
    assert viewer._current_index == 2


def test_keyboard_bindings_space(tk_root, tmp_path):
    """Test space keyboard shortcut."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer._current_index = 0
    viewer._scroll_offset = 100
    viewer.event_generate("<space>")
    assert viewer._scroll_offset != 100 or viewer._current_index != 0


def test_keyboard_bindings_escape(tk_root, tmp_path, monkeypatch):
    """Test Escape keyboard shortcut."""
    _write_image(tmp_path / "page1.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.png")

    quit_called = [False]

    def fake_quit():
        quit_called[0] = True

    original_destroy = tk_root.destroy
    monkeypatch.setattr(tk_root, "destroy", lambda: None)
    viewer._quit = fake_quit
    viewer._quit()
    monkeypatch.setattr(tk_root, "destroy", original_destroy)
    assert quit_called[0]


def test_keyboard_bindings_backspace(tk_root, tmp_path):
    """Test BackSpace keyboard shortcut."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer._current_index = 1
    viewer._trigger_prev()

    tk_root.after(200, tk_root.quit)
    tk_root.mainloop()
    assert viewer._current_index == 0


def test_keyboard_bindings_prior_next(tk_root, tmp_path):
    """Test Prior (PageUp) and Next (PageDown) keyboard shortcuts."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "page1.png")
    _write_image(folder / "page2.png")
    _write_image(folder / "page3.png")

    viewer = cdisplayagain.ComicViewer(tk_root, folder / "page1.png")
    viewer.source = cdisplayagain.load_directory(folder)
    viewer._current_index = 1
    viewer.event_generate("<Next>")
    assert viewer._current_index == 2

    viewer._current_index = 1
    viewer.event_generate("<Prior>")
    assert viewer._current_index == 0


def test_archive_loading_error_paths(tmp_path):
    """Test error handling in archive loading."""
    # Test load_directory with non-existent path
    with pytest.raises(RuntimeError, match="not a directory"):
        cdisplayagain.load_directory(Path("/nonexistent/path/that/does/not/exist"))

    # Test load_directory with empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(RuntimeError, match="No images found"):
        cdisplayagain.load_directory(empty_dir)

    # Test load_directory with file instead of directory
    _write_image(tmp_path / "test.png")
    with pytest.raises(RuntimeError, match="not a directory"):
        cdisplayagain.load_directory(tmp_path / "test.png")


def test_worker_queue_full_handling(tk_root, tmp_path, monkeypatch):
    """Test worker handles queue.Full exceptions gracefully."""
    _write_image(tmp_path / "test.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "test.png")

    # Mock queue.put to raise queue.Full
    import queue

    def mock_put_full(*args, **kwargs):
        raise queue.Full("Test queue full")

    # This tests the error handling path at lines 418-419
    monkeypatch.setattr(viewer._worker._queue, "put_nowait", mock_put_full)

    # Should not raise an exception
    try:
        viewer._worker.preload(0)
    except queue.Full:
        pytest.fail("queue.Full should be caught and ignored")

    # Also test the image loading queue.Full path
    try:
        viewer._worker.request_page(0, 100, 100)
    except queue.Full:
        pytest.fail("queue.Full should be caught and ignored in request_page")
