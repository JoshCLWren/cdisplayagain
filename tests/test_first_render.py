"""Test first render behavior without preview."""

import cdisplayagain


def test_first_render_skips_preview(tmp_path, tk_root):
    """Verify that first render skips fast preview to avoid tiny images."""
    cbz_path = tmp_path / "first_render_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    assert not app._first_proper_render_completed, "First render should not be completed yet"

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    assert cache_key not in app._image_cache, "Cache should be empty initially"

    app._render_current_sync()

    assert not app._first_proper_render_completed, (
        "Preview-only render should not mark as completed"
    )
    assert app._tk_img is None, "No image should be displayed yet (worker processing)"


def test_first_render_from_cache_marks_completed(tmp_path, tk_root):
    """Verify that first render from cache marks proper render as completed."""
    cbz_path = tmp_path / "cache_hit_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    assert not app._first_proper_render_completed

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    if app.source:
        raw_bytes = app.source.get_bytes(app.source.pages[0])
        from image_backend import get_resized_pil

        resized_img = get_resized_pil(raw_bytes, cw, ch)
        app._image_cache[cache_key] = resized_img

    app._render_current_sync()

    assert app._first_proper_render_completed, "Cache hit should mark as completed"
    assert app._tk_img is not None, "Image should be displayed from cache"


def test_second_render_shows_preview(tmp_path, tk_root):
    """Verify that subsequent renders show fast preview before high-quality version."""
    cbz_path = tmp_path / "preview_test.cbz"
    create_benchmark_cbz(cbz_path, page_count=3)

    app = cdisplayagain.ComicViewer(tk_root, cbz_path)
    app.canvas.config(width=1920, height=1080)
    app.update_idletasks()

    cw = max(1, app.canvas.winfo_width())
    ch = max(1, app.canvas.winfo_height())
    cache_key = (0, cw, ch)

    if app.source:
        raw_bytes = app.source.get_bytes(app.source.pages[0])
        from image_backend import get_resized_pil

        resized_img = get_resized_pil(raw_bytes, cw, ch)
        app._image_cache[cache_key] = resized_img

    app._render_current_sync()
    assert app._first_proper_render_completed, "First render should be completed"

    app.next_page()
    app.update_idletasks()

    assert app._current_index == 1, "Should be on second page"
    cache_key_1 = (1, cw, ch)
    assert cache_key_1 not in app._image_cache, "Second page should not be cached"

    app._render_current_sync()

    assert app._tk_img is not None, "Preview should be displayed immediately"
    assert app._first_proper_render_completed, "Should still be marked as completed"


def create_benchmark_cbz(path, page_count=1):
    """Create a minimal CBZ for testing."""
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    with ZipFile(path, "w") as zf:
        for i in range(page_count):
            zf.writestr(f"page_{i:02d}.jpg", buf.getvalue())
