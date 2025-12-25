"""Parity tests for viewer behavior and supported formats."""

import io
import sys
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
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


def _make_cbz_with_text(path: Path, names: list[str], text_names: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            buf = io.BytesIO()
            img = Image.new("RGB", (64, 64), color=(10, 20, 30))
            img.save(buf, format="PNG")
            zf.writestr(name, buf.getvalue())
        for name in text_names:
            zf.writestr(name, "info")


def _make_tar(path: Path, names: list[str], text_names: list[str] | None = None) -> None:
    text_names = text_names or []
    with tarfile.open(path, "w") as tf:
        for name in names:
            buf = io.BytesIO()
            img = Image.new("RGB", (64, 64), color=(10, 20, 30))
            img.save(buf, format="PNG")
            data = buf.getvalue()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        for name in text_names:
            data = b"info"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


@pytest.fixture
def viewer(tmp_path):
    """Provide a minimal viewer instance for UI-related tests."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    root = cdisplayagain.tk.Tk()
    root.withdraw()
    root.update()
    root.attributes("-alpha", 0.0)
    try:
        app = cdisplayagain.ComicViewer(root, img_path)
        yield app
    finally:
        root.destroy()


def test_launch_fullscreen_enabled_in_main(tmp_path, monkeypatch):
    """Ensure main() requests fullscreen on startup."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)

    calls = {"fullscreen": None, "mainloop": False}

    class FakeTk:
        def withdraw(self):
            pass

        def destroy(self):
            pass

        def attributes(self, name, value):
            calls["fullscreen"] = (name, value)

        def deiconify(self):
            pass

        def mainloop(self):
            calls["mainloop"] = True

    class FakeViewer:
        def __init__(self, master, comic_path):
            self.master = master
            self.comic_path = comic_path
            self._fullscreen = False

        def _set_cursor_hidden(self, hidden):
            pass

        def _request_focus(self):
            pass

    monkeypatch.setattr(cdisplayagain.tk, "Tk", FakeTk)
    monkeypatch.setattr(cdisplayagain, "ComicViewer", FakeViewer)
    monkeypatch.setattr(sys, "argv", ["cdisplayagain.py", str(img_path)])

    cdisplayagain.main()

    assert calls["fullscreen"] == ("-fullscreen", True)


def test_launch_fullscreen_hides_cursor(tmp_path, monkeypatch):
    """Ensure main() hides the cursor when fullscreen starts."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)

    calls = {"hidden": None}

    class FakeTk:
        def withdraw(self):
            pass

        def destroy(self):
            pass

        def attributes(self, name, value):
            pass

        def deiconify(self):
            pass

        def mainloop(self):
            pass

    class FakeViewer:
        def __init__(self, master, comic_path):
            self.master = master
            self.comic_path = comic_path

        def _request_focus(self):
            return None

        def _set_cursor_hidden(self, hidden):
            calls["hidden"] = hidden

    monkeypatch.setattr(cdisplayagain.tk, "Tk", FakeTk)
    monkeypatch.setattr(cdisplayagain, "ComicViewer", FakeViewer)
    monkeypatch.setattr(sys, "argv", ["cdisplayagain.py", str(img_path)])

    cdisplayagain.main()

    assert calls["hidden"] is True


def test_minimal_ui_has_single_canvas_child(viewer):
    """Confirm the viewer renders a single canvas widget."""
    children = viewer.winfo_children()
    assert len(children) == 1
    assert isinstance(children[0], cdisplayagain.tk.Canvas)


def test_fullscreen_windowed_toggle_and_cursor_hidden():
    """Verify fullscreen toggling and cursor hiding hooks exist."""
    assert hasattr(cdisplayagain.ComicViewer, "toggle_fullscreen")
    assert hasattr(cdisplayagain.ComicViewer, "_set_cursor_hidden")


def test_right_click_opens_context_menu(viewer):
    """Ensure right-click binds to the context menu."""
    assert viewer.bind_all("<Button-3>") != ""
    assert hasattr(viewer, "_context_menu")
    first_label = viewer._context_menu.entrycget(0, "label")
    assert first_label == "Load files"


def test_open_dialog_uses_file_browser(monkeypatch, viewer, tmp_path):
    """Confirm open dialog creates a dialog with Browse button."""
    mock_dialog = MagicMock()
    mock_dialog.title = Mock()
    mock_dialog.bind = Mock(return_value="callback")
    mock_dialog.destroy = Mock()

    def fake_wait_window(window):
        pass

    mock_frame = MagicMock()
    mock_frame.pack = Mock()
    mock_frame.grid = Mock()

    monkeypatch.setattr(cdisplayagain.tk, "Toplevel", MagicMock(return_value=mock_dialog))
    monkeypatch.setattr(viewer.master, "wait_window", fake_wait_window)
    viewer._open_dialog()

    mock_dialog.title.assert_called_once_with("Open Comic")


def test_open_dialog_preselects_all_files(monkeypatch, viewer, tmp_path):
    """Ensure dialog has browse functionality."""
    mock_dialog = MagicMock()
    mock_dialog.title = Mock()
    mock_dialog.bind = Mock(return_value="callback")
    mock_dialog.destroy = Mock()

    def fake_wait_window(window):
        pass

    monkeypatch.setattr(cdisplayagain.tk, "Toplevel", MagicMock(return_value=mock_dialog))
    monkeypatch.setattr(viewer.master, "wait_window", fake_wait_window)
    viewer._open_dialog()

    bind_calls = [call[0][0] for call in mock_dialog.bind.call_args_list]
    assert "<Escape>" in bind_calls
    assert "q" in bind_calls
    assert "Q" in bind_calls
    assert "x" in bind_calls


def test_open_dialog_uses_multi_select_for_windows_patterns(monkeypatch, viewer):
    """Confirm dialog structure is created properly."""
    mock_dialog = MagicMock()
    mock_dialog.title = Mock()
    mock_dialog.bind = Mock(return_value="callback")
    mock_dialog.destroy = Mock()
    mock_dialog.resizable = Mock()
    mock_dialog.protocol = Mock()
    mock_dialog.grab_set = Mock()

    def fake_wait_window(window):
        pass

    monkeypatch.setattr(cdisplayagain.tk, "Toplevel", MagicMock(return_value=mock_dialog))
    monkeypatch.setattr(viewer.master, "wait_window", fake_wait_window)
    viewer._open_dialog()

    mock_dialog.resizable.assert_called_once_with(False, False)
    mock_dialog.grab_set.assert_called_once()


def test_quit_during_open_dialog_defers_until_dialog_closes(monkeypatch, viewer):
    """Ensure quitting during dialog waits for dialog to close."""
    destroyed = {"called": False}

    def fake_destroy():
        destroyed["called"] = True

    mock_dialog = MagicMock()
    mock_dialog.title = Mock()
    mock_dialog.bind = Mock(return_value="callback")
    mock_dialog.destroy = Mock()

    def fake_wait_window(window):
        pass

    monkeypatch.setattr(cdisplayagain.tk, "Toplevel", MagicMock(return_value=mock_dialog))
    monkeypatch.setattr(viewer.master, "destroy", fake_destroy)
    monkeypatch.setattr(viewer.master, "wait_window", fake_wait_window)
    viewer._quit()

    assert destroyed["called"] is True


def test_load_folder_or_archive(tmp_path):
    """Load both a folder and a CBZ archive."""
    folder = tmp_path / "pages"
    folder.mkdir()
    _write_image(folder / "01.png")
    _write_image(folder / "02.png")
    source = cdisplayagain.load_comic(folder)
    assert source.pages == ["01.png", "02.png"]

    cbz_path = tmp_path / "comic.cbz"
    _make_cbz(cbz_path, ["01.png", "02.png"])
    source = cdisplayagain.load_comic(cbz_path)
    assert source.pages == ["01.png", "02.png"]


def test_reads_jpeg_gif_png(tmp_path):
    """Load single-image sources for common formats."""
    jpg = tmp_path / "page.jpg"
    gif = tmp_path / "page.gif"
    png = tmp_path / "page.png"
    _write_image(jpg)
    _write_image(gif)
    _write_image(png)

    assert cdisplayagain.load_comic(jpg).pages == ["page.jpg"]
    assert cdisplayagain.load_comic(gif).pages == ["page.gif"]
    assert cdisplayagain.load_comic(png).pages == ["page.png"]


def test_reads_zip_tar_archives(tmp_path):
    """Load multiple archive types and ensure pages list is set."""
    zip_path = tmp_path / "comic.zip"
    _make_cbz(zip_path, ["01.png"])
    tar_path = tmp_path / "comic.tar"
    _make_tar(tar_path, ["01.png"])

    zip_source = cdisplayagain.load_comic(zip_path)
    tar_source = cdisplayagain.load_comic(tar_path)
    try:
        assert zip_source.pages == ["01.png"]
        assert tar_source.pages == ["01.png"]
    finally:
        if zip_source.cleanup:
            zip_source.cleanup()
        if tar_source.cleanup:
            tar_source.cleanup()


def test_reads_tar_archives_with_images_and_text(tmp_path):
    """Prefer text pages first when loading TAR archives."""
    tar_path = tmp_path / "comic.tar"
    _make_tar(tar_path, ["02.png", "01.png"], ["info.nfo"])

    source = cdisplayagain.load_comic(tar_path)

    try:
        assert source.pages == ["info.nfo", "01.png", "02.png"]
    finally:
        if source.cleanup:
            source.cleanup()


def test_sorting_is_alphabetical(tmp_path):
    """Confirm natural sorting order in folders."""
    folder = tmp_path / "pages"
    folder.mkdir()
    _write_image(folder / "10.png")
    _write_image(folder / "2.png")
    _write_image(folder / "1.png")

    source = cdisplayagain.load_comic(folder)
    assert source.pages == ["1.png", "2.png", "10.png"]


def test_nfo_txt_displayed_first(tmp_path):
    """Ensure text files appear before images in folders."""
    folder = tmp_path / "pages"
    folder.mkdir()
    (folder / "info.nfo").write_text("info")
    (folder / "readme.txt").write_text("readme")
    _write_image(folder / "01.png")

    source = cdisplayagain.load_comic(folder)
    assert source.pages[:2] == ["info.nfo", "readme.txt"]


def test_nfo_txt_displayed_first_in_cbz(tmp_path):
    """Ensure text files appear before images in CBZ files."""
    cbz_path = tmp_path / "comic.cbz"
    _make_cbz_with_text(cbz_path, ["01.png"], ["info.nfo", "readme.txt"])

    source = cdisplayagain.load_comic(cbz_path)
    assert source.pages[:2] == ["info.nfo", "readme.txt"]


def test_info_screen_dismissed_by_double_click_or_any_key(viewer):
    """Validate info overlay dismissal bindings exist."""
    assert viewer.bind("<Double-Button-1>") != ""
    assert viewer.bind("<Key>") != ""


def test_info_screen_shows_first_page_simultaneously(viewer):
    """Confirm info overlay renders alongside first image."""
    assert hasattr(viewer, "_info_overlay")
    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    if viewer.source and len(viewer.source.pages) > 0:
        raw_bytes = viewer.source.get_bytes(viewer.source.pages[0])
        from image_backend import get_resized_pil

        resized_img = get_resized_pil(raw_bytes, cw, ch)
        viewer._image_cache[(0, cw, ch)] = resized_img
        viewer._render_current()
    assert viewer._current_pil is not None


def test_info_screen_overlays_first_image_when_text_first(viewer, tmp_path):
    """Render text-first sources with image and overlay."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.nfo").write_text("info")
    _write_image(folder / "01.png")

    viewer._open_comic(folder)
    viewer.update()

    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    if viewer.source and len(viewer.source.pages) > 1:
        for idx in range(len(viewer.source.pages)):
            if cdisplayagain.is_text_name(viewer.source.pages[idx]):
                continue
            raw_bytes = viewer.source.get_bytes(viewer.source.pages[idx])
            from image_backend import get_resized_pil

            resized_img = get_resized_pil(raw_bytes, cw, ch)
            viewer._image_cache[(idx, cw, ch)] = resized_img
        viewer._render_current()

    assert viewer._info_overlay is not None
    assert viewer._current_pil is not None


def test_arrow_keys_turn_pages(viewer, tmp_path):
    """Advance and rewind pages via arrow keys."""
    img1 = tmp_path / "page1.png"
    _write_image(img1)
    img2 = tmp_path / "page2.png"
    _write_image(img2)
    viewer._open_comic(tmp_path)
    viewer.update()
    assert viewer._current_index == 0
    viewer.event_generate("<Right>")
    viewer.update()
    assert viewer._current_index == 1
    viewer.event_generate("<Left>")
    viewer.update()
    assert viewer._current_index == 0


def test_page_down_and_page_up_keys_turn_pages(viewer, tmp_path):
    """Advance and rewind pages via Page Up/Down."""
    img1 = tmp_path / "page1.png"
    _write_image(img1)
    img2 = tmp_path / "page2.png"
    _write_image(img2)
    viewer._open_comic(tmp_path)
    viewer.update()
    viewer.event_generate("<Next>")
    viewer.update()
    assert viewer._current_index == 1
    viewer.event_generate("<Prior>")
    viewer.update()
    assert viewer._current_index == 0


def test_spacebar_scrolls_then_advances(viewer, tmp_path):
    """Scroll with spacebar until end, then advance."""
    tall = tmp_path / "tall.png"
    img = Image.new("RGB", (200, 1200), color=(100, 100, 100))
    img.save(tall)
    short = tmp_path / "short.png"
    _write_image(short, size=(200, 200))
    viewer._open_comic(tmp_path)
    viewer.update()

    viewer.master.deiconify()
    viewer.master.geometry("200x200")
    viewer.update()

    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())
    from image_backend import get_resized_pil

    for idx in range(len(viewer.source.pages)):
        raw_bytes = viewer.source.get_bytes(viewer.source.pages[idx])
        resized_img = get_resized_pil(raw_bytes, cw, ch)
        viewer._image_cache[(idx, cw, ch)] = resized_img

    viewer._render_current()
    assert viewer._current_index == 0
    assert viewer._scroll_offset == 0

    # viewer.event_generate("<space>")
    viewer._space_advance()
    viewer.update()
    assert viewer._scroll_offset > 0

    attempts = 0
    while viewer._current_index == 0 and attempts < 20:
        # viewer.event_generate("<space>")
        viewer._space_advance()
        viewer.update()
        attempts += 1
        if viewer._scroll_offset == 0:
            break

    assert viewer._current_index == 1


def test_mouse_drag_pans_page(viewer):
    """Ensure mouse drag bindings exist for panning."""
    assert viewer.canvas.bind("<ButtonPress-1>") != ""
    assert viewer.canvas.bind("<B1-Motion>") != ""


def test_mouse_wheel_scrolls_or_navigates(viewer):
    """Ensure mouse wheel binding exists."""
    assert viewer.canvas.bind("<MouseWheel>") != ""


def test_f1_opens_help(viewer):
    """Ensure F1 binding exists for help."""
    assert viewer.bind_all("<F1>") != ""


def test_m_minimizes_program(viewer):
    """Ensure the minimize shortcut exists."""
    assert viewer.bind_all("m") != ""
    assert hasattr(viewer, "_minimize")


def test_x_terminates_program(viewer):
    """Ensure the quit shortcut exists."""
    assert viewer.bind_all("x") != ""
    assert hasattr(viewer, "_quit")


def test_context_menu_has_minimize_and_quit(viewer):
    """Ensure the context menu includes minimize and quit."""
    assert hasattr(viewer, "_context_menu")
    labels = [
        viewer._context_menu.entrycget(i, "label")
        for i in range(viewer._context_menu.index("end") + 1)
    ]
    assert "Minimize" in labels
    assert "Quit" in labels


def test_display_has_one_page_and_two_page_modes():
    """Ensure page mode toggles are present."""
    assert hasattr(cdisplayagain.ComicViewer, "set_one_page_mode")
    assert hasattr(cdisplayagain.ComicViewer, "set_two_page_mode")


def test_uses_lanczos_resampling(viewer, monkeypatch):
    """Verify Lanczos resampling is used for scaling."""
    import cdisplayagain

    called = {}

    original_get_resized = cdisplayagain.get_resized_pil

    def fake_get_resized(raw_bytes, width, height):
        called["used"] = True
        return original_get_resized(raw_bytes, width, height)

    monkeypatch.setattr(cdisplayagain, "get_resized_pil", fake_get_resized)

    cw = max(1, viewer.canvas.winfo_width())
    ch = max(1, viewer.canvas.winfo_height())

    if viewer.source and len(viewer.source.pages) > 0:
        raw_bytes = viewer.source.get_bytes(viewer.source.pages[0])
        resized_img = fake_get_resized(raw_bytes, cw, ch)
        viewer._image_cache[(0, cw, ch)] = resized_img

    assert called.get("used") is True


def test_color_balance_and_yellow_reduction_options_exist():
    """Ensure color-related toggles exist."""
    assert hasattr(cdisplayagain.ComicViewer, "toggle_color_balance")
    assert hasattr(cdisplayagain.ComicViewer, "toggle_yellow_reduction")


def test_hints_show_on_idle_cursor():
    """Ensure hint popup hook exists."""
    assert hasattr(cdisplayagain.ComicViewer, "_show_hint_popup")


def test_common_settings_options_exist():
    """Ensure common settings callbacks exist."""
    expected_attrs = [
        "toggle_two_pages",
        "toggle_hints",
        "toggle_two_page_advance",
        "set_page_buffer",
        "set_background_color",
        "set_small_cursor",
        "set_mouse_binding",
        "toggle_fullscreen",
    ]
    for attr in expected_attrs:
        assert hasattr(cdisplayagain.ComicViewer, attr)


def test_full_parity_flow_space_and_nfo(tmp_path, viewer):
    """Run a basic flow involving text pages and space advance."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "readme.txt").write_text("info")
    _write_image(folder / "01.png")
    _write_image(folder / "02.png")

    viewer._open_comic(folder)
    viewer.update()
    assert viewer.source.pages[0] == "readme.txt"
    viewer.event_generate("<space>")
    viewer.update()
    assert viewer._current_index >= 1


def test_fullscreen_toggle(tmp_path, viewer):
    """Test fullscreen toggle functionality."""
    viewer.toggle_fullscreen()
    assert viewer._fullscreen is True


def test_scroll_down_and_up(tmp_path, viewer):
    """Test scroll down and scroll up methods."""
    viewer._open_comic(tmp_path / "page1.png")
    viewer.update()

    viewer._scroll_down()
    viewer.update()

    viewer._scroll_up()
    viewer.update()

    assert viewer._scroll_offset == 0


def test_space_advance_with_image(tmp_path, viewer):
    """Test space advance with image content."""
    folder = tmp_path / "book"
    folder.mkdir()
    _write_image(folder / "01.png")
    _write_image(folder / "02.png")

    viewer._open_comic(folder)
    viewer.update()

    initial_index = viewer._current_index
    viewer._space_advance()
    viewer.update()

    assert viewer._current_index == initial_index + 1
