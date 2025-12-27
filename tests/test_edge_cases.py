"""Edge case and integration tests for cdisplayagain."""

import io
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import cdisplayagain


def _write_image(path: Path, size=(10, 10), color=(0, 0, 0)) -> None:
    img = Image.new("RGB", size, color=color)
    img.save(path)


def _create_invalid_zip(path: Path) -> None:
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 100 + b"invalid data")


def _create_invalid_tar(path: Path) -> None:
    path.write_bytes(b"not a tar file at all")


def test_load_comic_with_corrupted_cbz(tmp_path):
    """Test loading corrupted CBZ file raises appropriate error."""
    cbz_path = tmp_path / "corrupted.cbz"
    _create_invalid_zip(cbz_path)

    with pytest.raises(zipfile.BadZipFile):
        cdisplayagain.load_comic(cbz_path)


def test_load_comic_with_corrupted_cbr(tmp_path):
    """Test loading corrupted CBR file raises appropriate error."""
    cbr_path = tmp_path / "corrupted.cbr"
    cbr_path.write_bytes(b"not a rar file")

    with pytest.raises((RuntimeError, zipfile.BadZipFile, Exception)):
        cdisplayagain.load_comic(cbr_path)


def test_load_comic_with_corrupted_tar(tmp_path):
    """Test loading corrupted TAR file raises appropriate error."""
    tar_path = tmp_path / "corrupted.tar"
    _create_invalid_tar(tar_path)

    with pytest.raises(RuntimeError, match="Could not open TAR"):
        cdisplayagain.load_comic(tar_path)


def test_load_cbz_with_only_text_files(tmp_path):
    """Test CBZ with only text files (no images) still works."""
    cbz_path = tmp_path / "text_only.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("readme.txt", b"info")
        zf.writestr("info.nfo", b"more info")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 2
        assert "readme.txt" in source.pages
        assert "info.nfo" in source.pages
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_tar_with_only_text_files(tmp_path):
    """Test TAR with only text files (no images) still works."""
    tar_path = tmp_path / "text_only.tar"
    with tarfile.open(tar_path, "w") as tf:
        data = b"data"
        info1 = tarfile.TarInfo("readme.txt")
        info1.size = len(data)
        tf.addfile(info1, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)
    try:
        assert len(source.pages) == 1
        assert "readme.txt" in source.pages
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_cbz_with_nested_directories(tmp_path):
    """Test CBZ with images in nested directories."""
    cbz_path = tmp_path / "nested.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("vol1/chapter1/page1.jpg", b"img1")
        zf.writestr("vol1/chapter1/page2.jpg", b"img2")
        zf.writestr("vol2/chapter1/page1.jpg", b"img3")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 3
        assert "vol1/chapter1/page1.jpg" in source.pages
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_tar_with_nested_directories(tmp_path):
    """Test TAR with images in nested directories."""
    tar_path = tmp_path / "nested.tar"
    with tarfile.open(tar_path, "w") as tf:
        for name in ["dir1/page1.jpg", "dir1/page2.jpg", "dir2/page1.jpg"]:
            data = b"data"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

    source = cdisplayagain.load_tar(tar_path)
    try:
        assert len(source.pages) == 3
        assert "dir1/page1.jpg" in source.pages
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_directory_with_nested_directories(tmp_path):
    """Test loading directory with nested subdirectories."""
    main_dir = tmp_path / "comic"
    main_dir.mkdir()
    (main_dir / "vol1").mkdir()
    (main_dir / "vol2").mkdir()
    _write_image(main_dir / "vol1" / "page1.jpg")
    _write_image(main_dir / "vol2" / "page1.jpg")

    source = cdisplayagain.load_directory(main_dir)
    assert len(source.pages) == 2


def test_load_cbz_with_mixed_case_extensions(tmp_path):
    """Test CBZ with mixed case file extensions."""
    cbz_path = tmp_path / "mixed_case.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page1.JPG", b"img1")
        zf.writestr("page2.Png", b"img2")
        zf.writestr("page3.jpeg", b"img3")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 3
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_cbz_with_unicode_filenames(tmp_path):
    """Test CBZ with unicode/non-ASCII filenames."""
    cbz_path = tmp_path / "unicode.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("café.jpg", b"img1")
        zf.writestr("日本語.png", b"img2")
        zf.writestr(" español.txt", b"info")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 3
        assert any("café" in p for p in source.pages)
    finally:
        if source.cleanup:
            source.cleanup()


def test_large_archive_cbz(tmp_path):
    """Test loading CBZ with many pages (large archive)."""
    cbz_path = tmp_path / "large.cbz"
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(100):
            img = Image.new("RGB", (100, 100), color=(i % 256, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page_{i:03d}.png", buf.getvalue())

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 100
        first_page = source.get_bytes(source.pages[0])
        assert len(first_page) > 0
    finally:
        if source.cleanup:
            source.cleanup()


def test_large_archive_directory(tmp_path):
    """Test loading directory with many images."""
    comic_dir = tmp_path / "large_comic"
    comic_dir.mkdir()
    for i in range(50):
        _write_image(comic_dir / f"page_{i:03d}.jpg", size=(100, 100))

    source = cdisplayagain.load_directory(comic_dir)
    assert len(source.pages) == 50


def test_load_cbz_with_duplicate_filenames(tmp_path):
    """Test CBZ with duplicate filenames (ZIP allows this)."""
    cbz_path = tmp_path / "duplicates.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page.jpg", b"first")
        zf.writestr("page.jpg", b"second")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert "page.jpg" in source.pages
        content = source.get_bytes("page.jpg")
        assert content == b"second" or content == b"first"
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_cbz_with_very_large_image(tmp_path):
    """Test CBZ with very large image dimensions."""
    cbz_path = tmp_path / "large_image.cbz"
    large_img = Image.new("RGB", (10000, 10000), color="red")
    buf = io.BytesIO()
    large_img.save(buf, format="PNG")

    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("huge.png", buf.getvalue())

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 1
        content = source.get_bytes("huge.png")
        assert len(content) > 0
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_directory_with_symlinks(tmp_path):
    """Test loading directory that contains symlinks."""
    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    _write_image(comic_dir / "page1.jpg")

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    _write_image(other_dir / "page2.jpg")

    (comic_dir / "link").symlink_to(other_dir / "page2.jpg")

    source = cdisplayagain.load_directory(comic_dir)
    assert "page1.jpg" in source.pages


def test_load_directory_with_hidden_files(tmp_path):
    """Test loading directory includes hidden files as-is."""
    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    _write_image(comic_dir / "page1.jpg")
    _write_image(comic_dir / ".hidden.jpg")
    _write_image(comic_dir / "..parent.jpg")

    source = cdisplayagain.load_directory(comic_dir)
    assert "page1.jpg" in source.pages
    assert ".hidden.jpg" in source.pages
    assert "..parent.jpg" in source.pages


def test_integration_open_read_quit_workflow(tk_root, tmp_path):
    """Integration test: open comic, navigate, quit."""
    _write_image(tmp_path / "page1.jpg", size=(100, 100))
    _write_image(tmp_path / "page2.jpg", size=(100, 100))
    _write_image(tmp_path / "page3.jpg", size=(100, 100))

    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "page1.jpg")
    viewer.source = cdisplayagain.load_directory(tmp_path)
    viewer.update()

    assert viewer.source is not None
    assert len(viewer.source.pages) == 3
    assert viewer._current_index == 0

    viewer.next_page()
    viewer.update()
    assert viewer._current_index == 1

    viewer.next_page()
    viewer.update()
    assert viewer._current_index == 2

    viewer.prev_page()
    viewer.update()
    assert viewer._current_index == 1

    viewer.first_page()
    viewer.update()
    assert viewer._current_index == 0

    viewer.last_page()
    viewer.update()
    assert viewer._current_index == 2


def test_integration_cbz_workflow(tk_root, tmp_path):
    """Integration test: full CBZ workflow."""
    cbz_path = tmp_path / "comic.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        for i in range(5):
            img = Image.new("RGB", (100, 100), color=(i * 50, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"page_{i}.png", buf.getvalue())

    viewer = cdisplayagain.ComicViewer(tk_root, cbz_path)
    viewer.update()

    assert viewer.source is not None
    assert len(viewer.source.pages) == 5

    for _ in range(4):
        initial_index = viewer._current_index
        viewer.next_page()
        viewer.update()
        assert viewer._current_index == initial_index + 1


def test_integration_directory_workflow(tk_root, tmp_path):
    """Integration test: full directory workflow."""
    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    for i in range(3):
        _write_image(comic_dir / f"page{i + 1}.jpg")

    viewer = cdisplayagain.ComicViewer(tk_root, comic_dir)
    viewer.update()

    assert viewer.source is not None
    assert len(viewer.source.pages) == 3

    viewer.first_page()
    viewer.update()
    assert viewer._current_index == 0

    viewer.last_page()
    viewer.update()
    assert viewer._current_index == 2


def test_integration_quit_cleanup(tk_root, tmp_path, monkeypatch):
    """Integration test: quit properly cleans up resources."""
    cleanup_called = [False]

    def track_cleanup():
        cleanup_called[0] = True

    _write_image(tmp_path / "dummy.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "dummy.png")
    viewer.source = cdisplayagain.PageSource(
        pages=["page.jpg"], get_bytes=lambda _: b"data", cleanup=track_cleanup
    )

    original_destroy = tk_root.destroy
    monkeypatch.setattr(tk_root, "destroy", lambda: None)

    viewer._quit()
    monkeypatch.setattr(tk_root, "destroy", original_destroy)

    assert cleanup_called[0]


def test_load_tar_with_only_directories(tmp_path):
    """Test TAR with only directories (no files) raises error."""
    tar_path = tmp_path / "only_dirs.tar"
    with tarfile.open(tar_path, "w") as tf:
        dir1 = tarfile.TarInfo("dir1/")
        dir1.type = tarfile.DIRTYPE
        tf.addfile(dir1)
        dir2 = tarfile.TarInfo("dir2/")
        dir2.type = tarfile.DIRTYPE
        tf.addfile(dir2)

    with pytest.raises(RuntimeError, match="No images"):
        cdisplayagain.load_tar(tar_path)


def test_load_cbz_with_directory_entries(tmp_path):
    """Test CBZ handles directory entries (names ending with /)."""
    cbz_path = tmp_path / "with_dirs.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("dir1/", b"")
        zf.writestr("dir1/page.jpg", b"img")
        zf.writestr("dir2/", b"")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert "dir1/page.jpg" in source.pages
        assert not any(p.endswith("/") for p in source.pages)
    finally:
        if source.cleanup:
            source.cleanup()


def test_invalid_image_data_in_archive(tmp_path):
    """Test archive with invalid image data."""
    cbz_path = tmp_path / "bad_img.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page1.jpg", b"valid image header but invalid data")
        zf.writestr("page2.jpg", b"not an image at all")

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        assert len(source.pages) == 2
        content = source.get_bytes("page1.jpg")
        assert len(content) > 0
    finally:
        if source.cleanup:
            source.cleanup()


def test_load_comic_nonexistent_path(tmp_path):
    """Test load_comic with nonexistent path."""
    nonexistent = tmp_path / "does_not_exist.png"
    with pytest.raises(RuntimeError):
        cdisplayagain.load_comic(nonexistent)


def test_open_comic_handles_load_errors(tk_root, tmp_path, monkeypatch):
    """Test _open_comic handles load errors gracefully."""
    cbz_path = tmp_path / "bad.cbz"
    _create_invalid_zip(cbz_path)

    _write_image(tmp_path / "dummy.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "dummy.png")
    original_source = viewer.source

    mock_showerror = MagicMock()
    monkeypatch.setattr(cdisplayagain.messagebox, "showerror", mock_showerror)

    viewer._open_comic(cbz_path)

    assert mock_showerror.called
    assert viewer.source is None or viewer.source == original_source


def test_load_directory_with_non_image_files(tmp_path):
    """Test directory with mixed file types loads only supported types."""
    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    _write_image(comic_dir / "page1.jpg")
    (comic_dir / "data.bin").write_bytes(b"binary data")
    (comic_dir / "script.sh").write_text("#!/bin/bash")
    (comic_dir / "info.txt").write_text("info")

    source = cdisplayagain.load_directory(comic_dir)
    assert "page1.jpg" in source.pages
    assert "info.txt" in source.pages
    assert "data.bin" not in source.pages
    assert "script.sh" not in source.pages


def test_load_cbz_preserves_natural_order(tmp_path):
    """Test CBZ with numbers maintains natural sort order."""
    cbz_path = tmp_path / "numbered.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        for num in [1, 2, 10, 20, 3, 30]:
            zf.writestr(f"page{num}.jpg", f"img{num}".encode())

    source = cdisplayagain.load_cbz(cbz_path)
    try:
        indices = [int(p.replace("page", "").replace(".jpg", "")) for p in source.pages]
        assert indices == [1, 2, 3, 10, 20, 30]
    finally:
        if source.cleanup:
            source.cleanup()


def test_image_worker_handles_invalid_image(tk_root, tmp_path, monkeypatch):
    """Test ImageWorker handles invalid image data gracefully."""
    cbz_path = tmp_path / "comic.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page.jpg", b"invalid image data")

    viewer = cdisplayagain.ComicViewer(tk_root, cbz_path)
    viewer.update()

    viewer._worker.request_page(0, 100, 100, preload=False, render_generation=0)


def test_get_bytes_missing_page(tk_root, tmp_path):
    """Test get_bytes with non-existent page name."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)

    viewer = cdisplayagain.ComicViewer(tk_root, img_path)
    viewer.source = cdisplayagain.load_directory(tmp_path)

    with pytest.raises((RuntimeError, FileNotFoundError)):
        viewer.source.get_bytes("nonexistent.jpg")


def test_cleanup_called_on_quit(tk_root, tmp_path, monkeypatch):
    """Test cleanup is called when viewer quits."""
    cleanup_called = [False]

    def fake_cleanup():
        cleanup_called[0] = True

    _write_image(tmp_path / "dummy.png")
    viewer = cdisplayagain.ComicViewer(tk_root, tmp_path / "dummy.png")
    viewer.source = cdisplayagain.PageSource(
        pages=["page.jpg"], get_bytes=lambda _: b"data", cleanup=fake_cleanup
    )

    original_destroy = tk_root.destroy
    monkeypatch.setattr(tk_root, "destroy", lambda: None)
    viewer._quit()
    monkeypatch.setattr(tk_root, "destroy", original_destroy)

    assert cleanup_called[0]


def test_load_comic_empty_directory(tmp_path):
    """Test load_comic with empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(RuntimeError, match="No images found"):
        cdisplayagain.load_comic(empty_dir)


def test_load_directory_with_only_readme_files(tmp_path):
    """Test directory with only readme files works."""
    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    (comic_dir / "readme.txt").write_text("info")
    (comic_dir / "info.nfo").write_text("more info")

    source = cdisplayagain.load_directory(comic_dir)
    assert "readme.txt" in source.pages
    assert "info.nfo" in source.pages
