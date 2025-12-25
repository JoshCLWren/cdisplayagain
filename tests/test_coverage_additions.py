"""Extra coverage for error paths and helpers."""

from __future__ import annotations

import _tkinter
import io
import logging
import shutil
import sys
import tarfile
import tempfile
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


def test_render_current_with_no_source_clears_canvas(tmp_path):
    """Clear canvas when rendering with no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = None
        viewer._render_current()
        assert viewer._canvas_image_id is None
    finally:
        root.destroy()


def test_render_info_with_image_no_following_image_clears_canvas(tmp_path):
    """Clear canvas when text file has no following image."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.nfo").write_text("info")
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = cdisplayagain.load_directory(folder)
        viewer.update()
        viewer._current_index = 0
        viewer._render_info_with_image("info.nfo")
        assert viewer._canvas_image_id is None
        assert viewer._current_pil is None
        assert viewer._scaled_size is None
        assert viewer._scroll_offset == 0
    finally:
        root.destroy()


def test_show_info_overlay_handles_decode_error(tmp_path):
    """Handle decode errors in text files gracefully."""
    folder = tmp_path / "book"
    folder.mkdir()
    img_path = folder / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = cdisplayagain.load_directory(folder)
        viewer.update()
        viewer._show_info_overlay("binary.bin")
        assert viewer._info_overlay is not None
    finally:
        root.destroy()


def test_reposition_current_image_with_no_image_id(tmp_path):
    """Handle repositioning when there's no canvas image."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer._canvas_image_id = None
        viewer._scaled_size = (100, 200)
        viewer._reposition_current_image()
    finally:
        root.destroy()


def test_reposition_current_image_with_no_scaled_size(tmp_path):
    """Handle repositioning when there's no scaled size."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.update()
        viewer._canvas_image_id = 123
        viewer._scaled_size = None
        viewer._reposition_current_image()
    finally:
        root.destroy()


def test_scroll_by_with_no_scaled_size(tmp_path):
    """Handle scrolling when there's no scaled size."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer._scaled_size = None
        viewer._scroll_by(100)
    finally:
        root.destroy()


def test_scroll_by_when_image_fits_on_screen(tmp_path):
    """Handle scrolling when image fits entirely on screen."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path, size=(10, 10))
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.update()
        initial_offset = viewer._scroll_offset
        viewer._scroll_by(100)
        assert viewer._scroll_offset == initial_offset
    finally:
        root.destroy()


def test_update_from_cache_with_no_source(tmp_path):
    """Handle cache update when there's no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = None
        from PIL import Image

        viewer._update_from_cache(0, Image.new("RGB", (10, 10)))
    finally:
        root.destroy()


def test_update_from_cache_with_wrong_index(tmp_path):
    """Handle cache update when index doesn't match current."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = None
        from PIL import Image

        viewer._update_from_cache(5, Image.new("RGB", (10, 10)))
    finally:
        root.destroy()


def test_minimize(tmp_path, monkeypatch):
    """Test minimize method handles errors gracefully."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)

        original_iconify = root.iconify

        def failing_iconify():
            raise _tkinter.TclError("error")

        monkeypatch.setattr(root, "iconify", failing_iconify)
        viewer._minimize()
        monkeypatch.setattr(root, "iconify", original_iconify)
    finally:
        root.destroy()


def test_show_help(tmp_path, monkeypatch):
    """Test help dialog can be shown."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)

        def mock_showinfo(*args, **kwargs):
            pass

        monkeypatch.setattr(cdisplayagain.messagebox, "showinfo", mock_showinfo)
        viewer._show_help()
    finally:
        root.destroy()


def test_log_mouse_event(tmp_path):
    """Test mouse event logging."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
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
    finally:
        root.destroy()


def test_start_pan(tmp_path):
    """Test pan start tracking."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        event = type("Event", (), {"y": 100})()
        viewer._start_pan(event)
        assert viewer._drag_start_y == 100
    finally:
        root.destroy()


def test_drag_pan(tmp_path):
    """Test pan drag handling."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer._drag_start_y = 100
        event = type("Event", (), {"y": 150})()
        viewer._drag_pan(event)
        assert viewer._drag_start_y == 150
    finally:
        root.destroy()


def test_drag_pan_without_start_y(tmp_path):
    """Handle pan drag when drag start is not set."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        if hasattr(viewer, "_drag_start_y"):
            delattr(viewer, "_drag_start_y")
        event = type("Event", (), {"y": 150})()
        viewer._drag_pan(event)
    finally:
        root.destroy()


def test_update_title_with_no_source(tmp_path):
    """Handle title update when there's no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = None
        viewer._update_title()
    finally:
        root.destroy()


def test_quit_with_cleanup(tmp_path):
    """Test quit method calls cleanup when available."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)

        cleanup_called = [False]

        def fake_cleanup():
            cleanup_called[0] = True

        viewer.source = cdisplayagain.PageSource(
            pages=[], get_bytes=lambda _: b"", cleanup=fake_cleanup
        )
        viewer._quit()
        assert cleanup_called[0]
    except _tkinter.TclError:
        pass


def test_show_info_overlay_no_source(tmp_path):
    """Handle info overlay when there's no source."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.source = None
        viewer._show_info_overlay("info.txt")
        assert viewer._info_overlay is None
    finally:
        root.destroy()


def test_on_mouse_wheel_no_delta(tmp_path):
    """Handle mouse wheel events with zero delta."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        event = type("Event", (), {"delta": 0})()
        viewer._on_mouse_wheel(event)
    finally:
        root.destroy()


def test_on_mouse_wheel_positive_delta_no_scroll(tmp_path):
    """Handle mouse wheel events with positive delta when image fits."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path, size=(10, 10))
    img2_path = tmp_path / "page2.png"
    _write_image(img2_path, size=(10, 10))
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    try:
        viewer = cdisplayagain.ComicViewer(root, img_path)
        viewer.update()
        event = type("Event", (), {"delta": 100})()
        viewer._on_mouse_wheel(event)
    finally:
        root.destroy()


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
