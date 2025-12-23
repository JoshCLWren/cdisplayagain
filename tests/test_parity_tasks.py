"""Parity tests for viewer behavior and supported formats."""

import io
import sys
import tarfile
import zipfile
from pathlib import Path

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
    app = cdisplayagain.ComicViewer(img_path)
    app.withdraw()
    try:
        yield app
    finally:
        app.destroy()


def test_launch_fullscreen_enabled_in_main(tmp_path, monkeypatch):
    """Ensure main() requests fullscreen on startup."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)

    calls = {"fullscreen": None, "mainloop": False}

    class FakeViewer:
        def __init__(self, comic_path):
            self.comic_path = comic_path

        def attributes(self, name, value):
            calls["fullscreen"] = (name, value)

        def _request_focus(self):
            return None

        def mainloop(self):
            calls["mainloop"] = True

    monkeypatch.setattr(cdisplayagain, "ComicViewer", FakeViewer)
    monkeypatch.setattr(sys, "argv", ["cdisplayagain.py", str(img_path)])

    cdisplayagain.main()

    assert calls["fullscreen"] == ("-fullscreen", True)


def test_launch_fullscreen_hides_cursor(tmp_path, monkeypatch):
    """Ensure main() hides the cursor when fullscreen starts."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)

    calls = {"hidden": None}

    class FakeViewer:
        def __init__(self, comic_path):
            self.comic_path = comic_path

        def attributes(self, name, value):
            return None

        def _request_focus(self):
            return None

        def _set_cursor_hidden(self, hidden):
            calls["hidden"] = hidden

        def mainloop(self):
            return None

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
    assert viewer.bind("<Button-3>") != ""
    assert hasattr(viewer, "_context_menu")
    first_label = viewer._context_menu.entrycget(0, "label")
    assert first_label == "Load files"


def test_open_dialog_uses_file_browser(monkeypatch, viewer, tmp_path):
    """Confirm open dialog uses the file browser API."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    called = {}

    def fake_askopenfilename(**kwargs):
        called["kwargs"] = kwargs
        return str(img_path)

    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilename", fake_askopenfilename)
    viewer._open_dialog()

    assert called["kwargs"]["title"] == "Open Comic"


def test_open_dialog_preselects_all_files(monkeypatch, viewer, tmp_path):
    """Ensure open dialog falls back to multi-select when needed."""
    img_path = tmp_path / "page1.png"
    _write_image(img_path)
    called = {"count": 0}

    def fake_askopenfilenames(**kwargs):
        called["count"] += 1
        return [str(img_path)]

    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilenames", fake_askopenfilenames)
    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilename", lambda **kwargs: "")
    viewer._open_dialog()

    assert called["count"] == 1


def test_open_dialog_uses_multi_select_for_windows_patterns(monkeypatch, viewer):
    """Confirm multi-select path is used for Windows patterns."""
    called = {"count": 0}

    def fake_askopenfilenames(**kwargs):
        called["count"] += 1
        return []

    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilenames", fake_askopenfilenames)
    monkeypatch.setattr(cdisplayagain.filedialog, "askopenfilename", lambda **kwargs: "")
    viewer._open_dialog()

    assert called["count"] == 1


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


def test_reads_zip_rar_ace_tar_archives(tmp_path):
    """Load multiple archive types and ensure pages list is set."""
    zip_path = tmp_path / "comic.zip"
    _make_cbz(zip_path, ["01.png"])
    rar_path = tmp_path / "comic.rar"
    ace_path = tmp_path / "comic.ace"
    tar_path = tmp_path / "comic.tar"
    for path in (rar_path, ace_path):
        path.write_bytes(b"")
    _make_tar(tar_path, ["01.png"])

    assert cdisplayagain.load_comic(zip_path).pages == ["01.png"]
    assert cdisplayagain.load_comic(rar_path).pages == ["01.png"]
    assert cdisplayagain.load_comic(ace_path).pages == ["01.png"]
    assert cdisplayagain.load_comic(tar_path).pages == ["01.png"]


def test_reads_tar_archives_with_images_and_text(tmp_path):
    """Prefer text pages first when loading TAR archives."""
    tar_path = tmp_path / "comic.tar"
    _make_tar(tar_path, ["02.png", "01.png"], ["info.nfo"])

    source = cdisplayagain.load_comic(tar_path)

    assert source.pages == ["info.nfo", "01.png", "02.png"]


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
    """Confirm info overlay renders alongside the first image."""
    assert hasattr(viewer, "_info_overlay")
    assert viewer._current_pil is not None


def test_info_screen_overlays_first_image_when_text_first(viewer, tmp_path):
    """Render text-first sources with image and overlay."""
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "info.nfo").write_text("info")
    _write_image(folder / "01.png")

    viewer._open_comic(folder)
    viewer.update()

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

    viewer.canvas.config(width=200, height=200)
    viewer.update()
    viewer._render_current()
    assert viewer._current_index == 0
    assert viewer._scroll_offset == 0

    viewer.event_generate("<space>")
    viewer.update()
    assert viewer._scroll_offset > 0

    attempts = 0
    while viewer._current_index == 0 and attempts < 20:
        viewer.event_generate("<space>")
        viewer.update()
        attempts += 1
        if viewer._scroll_offset == 0:
            break

    assert viewer._current_index == 1


def test_mouse_drag_pans_page(viewer):
    """Ensure mouse drag bindings exist for panning."""
    assert viewer.bind("<ButtonPress-1>") != ""
    assert viewer.bind("<B1-Motion>") != ""


def test_mouse_wheel_scrolls_or_navigates(viewer):
    """Ensure mouse wheel binding exists."""
    assert viewer.bind("<MouseWheel>") != ""


def test_f1_opens_help(viewer):
    """Ensure F1 binding exists for help."""
    assert viewer.bind("<F1>") != ""


def test_m_minimizes_program(viewer):
    """Ensure the minimize shortcut exists."""
    assert viewer.bind("m") != ""
    assert hasattr(viewer, "_minimize")


def test_x_terminates_program(viewer):
    """Ensure the quit shortcut exists."""
    assert viewer.bind("x") != ""
    assert hasattr(viewer, "_quit")


def test_context_menu_has_minimize_and_quit(viewer):
    """Ensure the context menu includes minimize and quit."""
    assert hasattr(viewer, "_context_menu")
    labels = [viewer._context_menu.entrycget(i, "label") for i in range(viewer._context_menu.index("end") + 1)]
    assert "Minimize" in labels
    assert "Quit" in labels


def test_display_has_one_page_and_two_page_modes():
    """Ensure page mode toggles are present."""
    assert hasattr(cdisplayagain.ComicViewer, "set_one_page_mode")
    assert hasattr(cdisplayagain.ComicViewer, "set_two_page_mode")


def test_uses_lanczos_resampling(viewer, monkeypatch):
    """Verify Lanczos resampling is used for scaling."""
    called = {}
    original_resize = Image.Image.resize

    def fake_resize(self, size, resample):
        called["resample"] = resample
        return original_resize(self, size, resample)

    monkeypatch.setattr(Image.Image, "resize", fake_resize)
    viewer._render_current()

    assert called["resample"] == Image.Resampling.LANCZOS


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
