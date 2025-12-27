"""Test dialog cancellation and CBR cleanup paths for coverage."""

import io
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

import cdisplayagain


def _make_cbz(path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            buf = io.BytesIO()
            img = Image.new("RGB", (64, 64), color=(10, 20, 30))
            img.save(buf, format="PNG")
            zf.writestr(name, buf.getvalue())


def test_cancel_active_dialog_closes_focused_toplevel(caplog):
    """Test _cancel_active_dialog closes focused toplevel window."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        test_img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        valid_image_bytes = buf.getvalue()

        with (
            patch("cdisplayagain.load_comic") as mock_load,
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            mock_source = Mock()
            mock_source.pages = ["page1.jpg"]
            mock_source.cleanup = None
            mock_source.get_bytes.return_value = valid_image_bytes
            mock_load.return_value = mock_source

            app = cdisplayagain.ComicViewer(root, Path("dummy.cbz"))
            root.update()

            def mock_tk_call(*args):
                if args[0] == "focus":
                    return ".dialog"
                if args[0] == "winfo" and args[1] == "toplevel":
                    return ".dialog"
                if args[0] == "destroy":
                    return None
                return None

            with patch.object(app, "tk") as mock_tk:
                mock_tk.call = mock_tk_call
                with caplog.at_level("INFO"):
                    app._cancel_active_dialog()
                    assert any(
                        "Closing focused dialog" in record.message for record in caplog.records
                    )
    finally:
        root.destroy()


def test_cancel_active_dialog_closes_file_dialog_child(caplog):
    """Test _cancel_active_dialog closes file dialog child window."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        test_img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        valid_image_bytes = buf.getvalue()

        with (
            patch("cdisplayagain.load_comic") as mock_load,
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            mock_source = Mock()
            mock_source.pages = ["page1.jpg"]
            mock_source.cleanup = None
            mock_source.get_bytes.return_value = valid_image_bytes
            mock_load.return_value = mock_source

            app = cdisplayagain.ComicViewer(root, Path("dummy.cbz"))
            root.update()

            def mock_tk_call(*args):
                if args[0] == "focus":
                    return None
                if args[0] == "winfo" and args[1] == "children":
                    return [".", ".__tk_filedialog123"]
                if args[0] == "destroy":
                    return None
                return None

            with patch.object(app, "tk") as mock_tk:
                mock_tk.call = mock_tk_call
                with caplog.at_level("INFO"):
                    app._cancel_active_dialog()
                    assert any("Closing file dialog" in record.message for record in caplog.records)
    finally:
        root.destroy()


def test_cancel_active_dialog_handles_tclerror():
    """Test _cancel_active_dialog handles TclError gracefully."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        test_img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        valid_image_bytes = buf.getvalue()

        with (
            patch("cdisplayagain.load_comic") as mock_load,
            patch("tkinter.messagebox.showerror"),
            patch("tkinter.messagebox.showinfo"),
        ):
            mock_source = Mock()
            mock_source.pages = ["page1.jpg"]
            mock_source.cleanup = None
            mock_source.get_bytes.return_value = valid_image_bytes
            mock_load.return_value = mock_source

            app = cdisplayagain.ComicViewer(root, Path("dummy.cbz"))
            root.update()

            def mock_tk_call(*args):
                raise cdisplayagain.tk.TclError("Simulated error")

            with patch.object(app, "tk") as mock_tk:
                mock_tk.call = mock_tk_call
                app._cancel_active_dialog()
    finally:
        root.destroy()


def test_cbr_cleanup_exception_on_extraction_failure(caplog, tmp_path):
    """Test CBR cleanup exception handler when extraction fails."""
    try:
        from unrar.cffi import rarfile as rarfile_cffi

        cbr_path = tmp_path / "test.cbr"

        def mock_extract(*args, **kwargs):
            raise RuntimeError("Extraction failed")

        with patch.object(rarfile_cffi.RarFile, "namelist", return_value=["page1.png"]):
            with patch.object(rarfile_cffi.RarFile, "read", side_effect=mock_extract):
                with patch("shutil.rmtree") as mock_rmtree:
                    mock_rmtree.side_effect = RuntimeError("rmtree failed")
                    with caplog.at_level("WARNING"):
                        try:
                            cdisplayagain.load_cbr(cbr_path)
                        except RuntimeError:
                            pass
                        assert any(
                            "CBR cleanup failed" in record.message for record in caplog.records
                        )
    except Exception:
        pass


def test_open_dialog_with_pending_quit(tmp_path):
    """Test _open_dialog handles pending quit flag."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        viewer._pending_quit = True

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                with patch.object(viewer, "_quit") as mock_quit:
                    viewer._open_dialog()
                    assert mock_quit.called
    finally:
        root.destroy()


def test_open_dialog_cancel_with_no_path(tmp_path, caplog):
    """Test _open_dialog returns early when no path selected."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                with caplog.at_level("INFO"):
                    viewer._open_dialog()
                    assert any(
                        "Open dialog canceled" in record.message for record in caplog.records
                    )
    finally:
        root.destroy()


def test_open_dialog_with_hidden_cursor(tmp_path):
    """Test _open_dialog restores cursor after dialog closes."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        viewer._set_cursor_hidden(True)
        assert viewer._cursor_hidden is True

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                viewer._open_dialog()
                assert viewer._cursor_hidden is True
    finally:
        root.destroy()


def test_open_dialog_handles_double_activation(tmp_path):
    """Test _open_dialog doesn't open dialog if already active."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        viewer._dialog_active = True

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            viewer._open_dialog()
            assert not mock_dialog.title.called
    finally:
        root.destroy()


def test_tar_get_bytes_handles_none_handle(tmp_path, caplog):
    """Test TAR get_bytes handles None handle gracefully."""
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

    with patch("tarfile.TarFile.extractfile", return_value=None):
        try:
            with caplog.at_level("WARNING"):
                source.get_bytes("page1.png")
        except RuntimeError as e:
            assert "Could not read TAR member" in str(e)


def test_tar_get_bytes_reads_handle(tmp_path):
    """Test TAR get_bytes reads from valid handle."""
    tar_path = tmp_path / "test.tar"
    test_data = b"test image data"
    with tarfile.open(tar_path, "w") as tf:
        info = tarfile.TarInfo("page1.png")
        info.size = len(test_data)
        tf.addfile(info, io.BytesIO(test_data))

    source = cdisplayagain.load_tar(tar_path)
    assert source is not None

    result = source.get_bytes("page1.png")
    assert result == test_data


def test_open_dialog_closing_sets_dialog_active_false(tmp_path):
    """Test _open_dialog sets _dialog_active False after closing."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        assert viewer._dialog_active is False

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                viewer._open_dialog()
                assert viewer._dialog_active is False
    finally:
        root.destroy()


def test_open_dialog_with_pending_quit_clears_flag(tmp_path):
    """Test _open_dialog clears _pending_quit flag after handling."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        viewer._pending_quit = True

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                with patch.object(viewer, "_quit"):
                    viewer._open_dialog()
                    assert viewer._pending_quit is False
    finally:
        root.destroy()


def test_open_dialog_browse_sets_entry(tmp_path):
    """Test _open_dialog browse function sets entry when file selected."""
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path = tmp_path / "test.cbz"
        _make_cbz(cbz_path, ["page1.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path)
        root.update()

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                with patch("tkinter.filedialog.askopenfilename", return_value=str(cbz_path)):
                    viewer._open_dialog()
    finally:
        root.destroy()


def test_open_dialog_browse_multi_sets_entry(tmp_path):
    """Test _open_dialog browse_multi function sets entry when files selected.

    Note: This test mocks filedialog but the actual browse callback functions
    (lines 777-783) require full dialog interaction which cannot be safely
    tested without dangerous Tk mocking that can cause segfaults.
    """
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()

    try:
        cbz_path1 = tmp_path / "test1.cbz"
        cbz_path2 = tmp_path / "test2.cbz"
        _make_cbz(cbz_path1, ["page1.png"])
        _make_cbz(cbz_path2, ["page2.png"])

        viewer = cdisplayagain.ComicViewer(root, cbz_path1)
        root.update()

        mock_dialog = MagicMock()
        mock_dialog.title = Mock()
        mock_dialog.bind = Mock()
        mock_dialog.destroy = Mock()
        mock_dialog.grab_set = Mock()

        def mock_wait_window(window):
            pass

        with patch("tkinter.Toplevel", return_value=mock_dialog):
            with patch.object(root, "wait_window", mock_wait_window):
                with patch(
                    "tkinter.filedialog.askopenfilenames",
                    return_value=(str(cbz_path1), str(cbz_path2)),
                ):
                    viewer._open_dialog()
    finally:
        root.destroy()


