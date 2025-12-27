#!/usr/bin/env python3
"""Lightweight comic reader inspired by CDisplay."""

from __future__ import annotations

import argparse
import importlib
import io
import logging
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import cast

from PIL import Image, ImageTk

from image_backend import get_resized_pil

TkPhotoImage = tk.PhotoImage | ImageTk.PhotoImage


def _as_wm(obj: tk.Misc) -> tk.Wm:
    """Treat a Misc (Tk root) as Wm for type checking."""
    return cast(tk.Wm, obj)


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
IMAGE_FILETYPE_PATTERN = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTS))
FILE_DIALOG_TYPES = [
    ("Comic Archives", "*.cbz *.cbr *.cbt *.cba *.tar *.zip *.rar *.ace"),
    ("Image Files", IMAGE_FILETYPE_PATTERN),
    (
        "All Supported",
        f"*.cbz *.cbr *.cbt *.cba *.tar *.zip *.rar *.ace {IMAGE_FILETYPE_PATTERN}".strip(),
    ),
    ("All files", "*.*"),
]

LOG_ROOT = Path(os.environ.get("CDISPLAYAGAIN_LOG_DIR", "logs")).expanduser()
LOG_PATH: Path | None = None
PERF_LOGGING = os.environ.get("CDISPLAYAGAIN_PERF") == "1"


def _init_logging() -> None:
    global LOG_PATH
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_dir = LOG_ROOT / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG_PATH = log_dir / "cdisplayagain.log"
    logging.basicConfig(
        filename=str(LOG_PATH),
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Logging initialized at %s", LOG_PATH)


def perf_log(operation: str, duration: float, extra: str = "") -> None:
    """Log performance metrics if perf logging is enabled."""
    if PERF_LOGGING:
        logging.info("PERF %s: %.6f%s %s", operation, duration, "s", extra)


class PerfTimer:
    """Context manager for timing operations."""

    def __init__(self, operation: str, extra: str = ""):
        """Initialize timer with operation name and extra metadata."""
        self.operation = operation
        self.extra = extra
        self.start_time: float | None = None

    def __enter__(self):
        """Start timing and return self."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log performance metric."""
        if self.start_time is not None:
            duration = time.perf_counter() - self.start_time
            perf_log(self.operation, duration, self.extra)
        return False


def natural_key(s: str):
    """Return a key for natural sorting with numeric segments."""
    # Natural sort: "10" > "2" correctly
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", s)]


def is_image_name(name: str) -> bool:
    """Return True when a path looks like a supported image."""
    return Path(name).suffix.casefold() in IMAGE_EXTS


def is_text_name(name: str) -> bool:
    """Return True when a path looks like an info text file."""
    return Path(name).suffix.casefold() in {".nfo", ".txt"}


class LRUCache:
    """Fixed-size LRU cache using OrderedDict for fast eviction."""

    def __init__(self, maxsize: int = 20):
        """Initialize LRU cache with maximum size."""
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()

    def get(self, key):
        """Get item and move to end (most recently used)."""
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def __setitem__(self, key, value):
        """Set item and evict oldest if at capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def __getitem__(self, key):
        """Get item with KeyError if missing, updates LRU order."""
        if key not in self._cache:
            raise KeyError(key)
        self._cache.move_to_end(key)
        return self._cache[key]

    def __contains__(self, key):
        """Check if key exists."""
        return key in self._cache

    def __len__(self):
        """Return number of cached items."""
        return len(self._cache)

    def clear(self):
        """Clear all cached items."""
        self._cache.clear()


@dataclass
class PageSource:
    """Abstraction over where pages come from."""

    pages: list[str]  # display/order names
    get_bytes: Callable[[str], bytes]
    cleanup: Callable[[], None] | None = None  # called on exit


class FocusRestorer:
    """Schedules focus-restoring callbacks without spamming Tk."""

    def __init__(
        self, after_idle: Callable[[Callable[[], None]], object], focus_fn: Callable[[], None]
    ):
        """Store Tk's idle scheduler and the focus callback."""
        self._after_idle = after_idle
        self._focus_fn = focus_fn
        self._pending = False

    def schedule(self) -> None:
        """Schedule a focus refresh if one is not already queued."""
        if self._pending:
            return
        self._pending = True
        self._after_idle(self._run)

    def _run(self) -> None:
        self._pending = False
        self._focus_fn()


class Debouncer:
    """Debounce rapid-fire events to prevent spam."""

    def __init__(self, delay_ms: int, callback: Callable, app):
        """Initialize with delay, callback, and Tk app reference."""
        self._delay = delay_ms
        self._callback = callback
        self._app = app
        self._timer_id: int | None = None

    def trigger(self, *args, **kwargs):
        """Trigger callback after delay (reset if already pending)."""
        if self._timer_id:
            self._app.after_cancel(self._timer_id)

        def wrapper():
            self._callback(*args, **kwargs)
            self._timer_id = None

        self._timer_id = self._app.after(self._delay, wrapper)


def load_cbz(path: Path) -> PageSource:
    """Load a CBZ/ZIP archive into a page source."""
    import zipfile

    zf = zipfile.ZipFile(path, "r")
    # Include images even if nested in directories inside the zip
    names = [n for n in zf.namelist() if not n.endswith("/")]
    text_names = [n for n in names if is_text_name(n)]
    image_names = [n for n in names if is_image_name(n)]
    text_names.sort(key=natural_key)
    image_names.sort(key=natural_key)
    pages = text_names + image_names

    if not pages:
        zf.close()
        raise RuntimeError("No images or info files found inside CBZ.")

    def get_bytes(name: str) -> bytes:
        return zf.read(name)

    def cleanup():
        try:
            zf.close()
        except Exception as e:
            logging.warning("Cleanup failed: %s", e)

    return PageSource(pages=pages, get_bytes=get_bytes, cleanup=cleanup)


def load_cbr(path: Path) -> PageSource:
    """Extract a CBR archive via unrar2-cffi and build a page source."""
    from unrar.cffi import rarfile as rarfile_cffi

    tmpdir = Path(tempfile.mkdtemp(prefix="cdisplayagain_"))
    try:
        with PerfTimer("load_cbr"):
            rar = rarfile_cffi.RarFile(str(path))
            filenames = rar.namelist()

            text_files: list[Path] = []
            image_files: list[Path] = []

            for filename in filenames:
                if not filename:
                    continue

                dest = tmpdir / filename
                if filename.endswith("/"):
                    dest.mkdir(parents=True, exist_ok=True)
                    continue

                try:
                    data = rar.read(filename)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)

                    if is_text_name(filename):
                        text_files.append(dest)
                    elif Path(filename).suffix.casefold() in IMAGE_EXTS:
                        image_files.append(dest)
                except Exception as e:
                    logging.warning("Failed to extract %s: %s", filename, e)

            text_files.sort(key=lambda p: natural_key(str(p.relative_to(tmpdir))))
            image_files.sort(key=lambda p: natural_key(str(p.relative_to(tmpdir))))

            if not text_files and not image_files:
                raise RuntimeError("No images or info files found after extracting CBR.")

            rel_names = [str(p.relative_to(tmpdir)) for p in text_files + image_files]

            def get_bytes(rel_name: str) -> bytes:
                return (tmpdir / rel_name).read_bytes()

            def cleanup():
                try:
                    shutil.rmtree(tmpdir)
                except Exception as e:
                    logging.warning("Cleanup failed: %s", e)

            return PageSource(pages=rel_names, get_bytes=get_bytes, cleanup=cleanup)
    except Exception:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            logging.warning("CBR cleanup failed: %s", e)
        raise


def load_tar(path: Path) -> PageSource:
    """Load a TAR archive into a page source."""
    import tarfile

    try:
        tf = tarfile.open(path, "r")
    except tarfile.TarError as exc:
        raise RuntimeError(f"Could not open TAR archive: {exc}") from exc

    members = [m for m in tf.getmembers() if m.isfile()]
    text_names = [m.name for m in members if is_text_name(m.name)]
    image_names = [m.name for m in members if is_image_name(m.name)]
    text_names.sort(key=natural_key)
    image_names.sort(key=natural_key)
    pages = text_names + image_names

    if not pages:
        tf.close()
        raise RuntimeError("No images or info files found inside TAR.")

    member_map = {m.name: m for m in members}

    def get_bytes(name: str) -> bytes:
        member = member_map.get(name)
        if not member:
            raise RuntimeError(f"Missing entry in TAR: {name}")
        handle = tf.extractfile(member)
        if handle is None:
            raise RuntimeError(f"Could not read TAR member: {name}")
        with handle:
            return handle.read()

    def cleanup():
        try:
            tf.close()
        except Exception as e:
            logging.warning("Cleanup failed: %s", e)

    return PageSource(pages=pages, get_bytes=get_bytes, cleanup=cleanup)


def load_directory(path: Path) -> PageSource:
    """Load a directory of images and text into a page source."""
    if not path.is_dir():
        raise RuntimeError("Provided path is not a directory")

    text_files = [
        p for p in path.rglob("*") if p.is_file() and p.suffix.casefold() in {".nfo", ".txt"}
    ]
    image_files = [p for p in path.rglob("*") if p.is_file() and is_image_name(p.name)]
    text_files.sort(key=lambda p: natural_key(str(p.relative_to(path))))
    image_files.sort(key=lambda p: natural_key(str(p.relative_to(path))))

    if not text_files and not image_files:
        raise RuntimeError("No images found in this directory.")

    rel_names = [str(p.relative_to(path)) for p in text_files + image_files]

    def get_bytes(rel_name: str) -> bytes:
        return (path / rel_name).read_bytes()

    return PageSource(pages=rel_names, get_bytes=get_bytes, cleanup=None)


def load_image_file(path: Path) -> PageSource:
    """Wrap a single image file as a one-page source."""
    if not path.is_file() or not is_image_name(path.name):
        raise RuntimeError("Not an image file")

    name = path.name

    def get_bytes(_: str) -> bytes:
        return path.read_bytes()

    return PageSource(pages=[name], get_bytes=get_bytes, cleanup=None)


class ImageWorker:
    """Background thread pool for image processing."""

    def __init__(self, app, num_workers: int = 4):
        """Initialize worker pool with app reference and start daemon threads."""
        self._app = app
        self._queue = queue.PriorityQueue(maxsize=4)
        self._threads: list[threading.Thread] = []
        for i in range(num_workers):
            thread = threading.Thread(target=self._run, daemon=True, name=f"ImageWorker-{i}")
            thread.start()
            self._threads.append(thread)

    def request_page(
        self, index: int, width: int, height: int, preload: bool = False, render_generation: int = 0
    ):
        """Request a page be processed in background."""
        try:
            priority = 1 if preload else 0
            self._queue.put_nowait((priority, index, width, height, preload, render_generation))
        except queue.Full:
            pass

    def preload(self, index: int):
        """Preload a page at current canvas dimensions for future display."""
        if not self._app:
            return
        cw = max(1, self._app.canvas.winfo_width())
        ch = max(1, self._app.canvas.winfo_height())
        self.request_page(index, cw, ch, preload=True)

    def _run(self):
        """Process resize requests in background."""
        while True:
            try:
                priority, index, width, height, preload, render_generation = self._queue.get()

                if preload:
                    logging.info("Worker preloading page %d at %dx%d", index, width, height)
                else:
                    logging.info("Worker processing page %d at %dx%d", index, width, height)

                if not preload and render_generation != self._app._render_generation:
                    logging.info(
                        "Worker cancelling stale render for page %d (gen %d != %d)",
                        index,
                        render_generation,
                        self._app._render_generation,
                    )
                    continue

                raw = self._app.source.get_bytes(self._app.source.pages[index])
                resized_pil = get_resized_pil(raw, width, height)

                if preload:
                    logging.info("Worker finished preloading page %d", index)
                else:
                    logging.info("Worker finished page %d, scheduling callback", index)

                self._app.after_idle(
                    lambda idx=index, img=resized_pil: self._app._update_from_cache(idx, img)
                )

            except Exception as e:
                logging.error("Image worker error: %s", e)


def load_comic(path: Path) -> PageSource:
    """Load a path containing a directory, archive, or image."""
    if path.is_dir():
        return load_directory(path)

    ext = path.suffix.casefold()
    if ext in {".cbz", ".zip"}:
        return load_cbz(path)
    if ext in {".cbr", ".rar", ".ace"}:
        if path.stat().st_size == 0:
            raise RuntimeError(f"Archive is empty: {path.name}")
        return load_cbr(path)
    if ext == ".tar":
        if path.stat().st_size == 0:
            raise RuntimeError(f"Archive is empty: {path.name}")
        return load_tar(path)
    if ext in IMAGE_EXTS:
        return load_image_file(path)
    raise RuntimeError("Unsupported type. Open a .cbz, .cbr, directory, or image file.")


class ComicViewer(tk.Frame):
    """Tk viewer for comic archives and image folders."""

    def __init__(self, master: tk.Tk, comic_path: Path):
        """Initialize the viewer frame and load the initial comic."""
        init_start = time.perf_counter()
        perf_log("app_init_start", 0, f"path={comic_path.name}")
        super().__init__(master)
        self.comic_path = comic_path
        self.pack(fill=tk.BOTH, expand=True)

        self.source: PageSource | None = None

        self._imagetk_ready = False
        self._prime_imagetk()
        self._cursor_name = "arrow"
        self._cursor_hidden = False
        self._fullscreen = False

        _as_wm(self.master).title(f"cdisplayagain - {comic_path.name}")
        self.configure(bg="#111111")
        cast(tk.Tk, self.master).configure(bg="#111111")
        self._configure_cursor()

        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.configure(cursor=self._cursor_name)

        # Keep reference to avoid Tk garbage-collecting the image
        self._tk_img: TkPhotoImage | None = None
        self._current_pil: Image.Image | None = None
        self._current_index: int = 0
        self._canvas_image_id: int | None = None

        # Lightweight caches - store PIL Image objects directly to avoid encode/decode roundtrip
        self._pil_cache: dict[str, Image.Image] = {}
        self._image_cache: LRUCache = LRUCache(maxsize=20)
        self._scroll_offset: int = 0
        self._scaled_size: tuple[int, int] | None = None
        self._focus_restorer = FocusRestorer(self.after_idle, self._ensure_focus)
        self._info_overlay: tk.Label | None = None
        self._context_menu = self._build_context_menu()
        self._dialog_active = False
        self._pending_quit: bool = False
        self._quitting: bool = False
        self._canvas_properly_sized: bool = False

        self._worker = ImageWorker(self)
        self._pending_index: int | None = None
        self._nav_debounce = Debouncer(150, self._execute_page_change, self)
        self._first_render_done: bool = False
        self._first_proper_render_completed: bool = False
        self._render_generation: int = 0

        self._bind_keys()
        self._bind_mouse()

        self.bind("<Map>", lambda _: self._request_focus())
        self.bind("<FocusIn>", lambda _: self._request_focus())
        self.bind("<Double-Button-1>", lambda _: self._dismiss_info())
        self.bind("<Key>", lambda _: self._dismiss_info())

        # Redraw on resize
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Load file - let Configure event trigger first render
        self._open_comic(comic_path)
        self._request_focus()

        perf_log("app_init_total", time.perf_counter() - init_start)

    def _request_focus(self) -> None:
        self._focus_restorer.schedule()

    def event_generate(self, sequence: str, **kwargs):
        """Intercept navigation keys to call viewer handlers."""
        if sequence in {"<Right>", "<Next>"}:
            self.next_page()
        elif sequence in {"<Left>", "<Prior>"}:
            self.prev_page()
        elif sequence == "<space>":
            self._space_advance()
        return super().event_generate(sequence, **kwargs)

    def _configure_cursor(self) -> None:
        """Use a minimal cursor to mimic CDisplay's pointer."""
        for cursor_name in ("none", "dotbox", "arrow"):
            try:
                self.configure(cursor=cursor_name)
                self._cursor_name = cursor_name
                return
            except tk.TclError:
                continue

    def _set_cursor_hidden(self, hidden: bool) -> None:
        self._cursor_hidden = hidden
        if hidden:
            cursor_name = "none"
            try:
                self.configure(cursor=cursor_name)
                self.canvas.configure(cursor=cursor_name)
                return
            except tk.TclError:
                cursor_name = self._cursor_name
        else:
            cursor_name = self._cursor_name

        try:
            self.configure(cursor=cursor_name)
            self.canvas.configure(cursor=cursor_name)
        except tk.TclError:
            pass

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen state and sync cursor visibility."""
        logging.info("Toggle fullscreen requested.")
        try:
            current = _as_wm(self.master).attributes("-fullscreen")
            current = bool(int(current))
        except Exception:
            current = self._fullscreen
        new_state = not current
        self._fullscreen = new_state
        try:
            _as_wm(self.master).attributes("-fullscreen", new_state)
        except tk.TclError:
            return
        self._set_cursor_hidden(new_state)

    def _ensure_focus(self) -> None:
        try:
            self.focus_force()
        except tk.TclError:
            pass
        self.canvas.focus_set()

    def _prime_imagetk(self) -> None:
        """Ensure Pillow's Tk bindings register the PyImagingPhoto command."""
        if self._imagetk_ready:
            return

        try:
            _imagingtk = importlib.import_module("PIL._imagingtk")
        except Exception as e:
            logging.warning("ImageTk initialization failed: could not import PIL._imagingtk: %s", e)
            return

        tkapp = getattr(self, "tk", None)
        if not tkapp or not hasattr(tkapp, "interpaddr"):
            logging.warning("ImageTk initialization failed: Tk interpreter not available")
            return

        try:
            interp_addr = tkapp.interpaddr()
        except Exception as e:
            logging.warning(
                "ImageTk initialization failed: could not get interpreter address: %s", e
            )
            return

        try:
            if isinstance(interp_addr, (bytes, bytearray)):
                interp_addr = int.from_bytes(interp_addr, sys.byteorder)
            elif isinstance(interp_addr, str):
                interp_addr = int(interp_addr, 0)
            else:
                interp_addr = int(interp_addr)
        except (ValueError, TypeError) as e:
            logging.warning(
                "ImageTk initialization failed: could not convert interpreter address: %s", e
            )
            return

        try:
            _imagingtk.tkinit(interp_addr)
        except Exception as e:
            logging.warning("ImageTk initialization failed: tkinit call failed: %s", e)
            return

        self._imagetk_ready = True

    def _photoimage_from_pil(self, img: Image.Image) -> tk.PhotoImage:
        rgb = img.convert("RGB")
        width, height = rgb.size
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        data = header + rgb.tobytes()
        return tk.PhotoImage(width=width, height=height, data=data, format="PPM", master=self)

    def _bind_keys(self):
        self.bind_all("<KeyPress>", self._log_key_event, add=True)
        self.bind_all("<Right>", lambda e: self._trigger_next())
        self.bind_all("<Left>", lambda e: self._trigger_prev())
        self.bind_all("<Next>", lambda e: self._trigger_next())
        self.bind_all("<Prior>", lambda e: self._trigger_prev())
        self.bind_all("<space>", lambda e: self._trigger_space())
        self.bind_all("<BackSpace>", lambda e: self._trigger_prev())
        self.bind_all("<Down>", lambda e: self._scroll_down())
        self.bind_all("<Up>", lambda e: self._scroll_up())
        self.bind_all("<Home>", lambda e: self.first_page())
        self.bind_all("<End>", lambda e: self.last_page())
        self.bind_all("<Escape>", lambda e: self._quit())
        self.bind_all("q", lambda e: self._quit())
        self.bind_all("Q", lambda e: self._quit())
        self.bind_all("x", lambda e: self._quit())
        self.bind_all("m", lambda e: self._minimize())
        self.bind_all("w", lambda e: self.toggle_fullscreen())
        self.bind_all("W", lambda e: self.toggle_fullscreen())
        self.bind_all("l", lambda e: self._open_dialog())
        self.bind_all("L", lambda e: self._open_dialog())
        self.bind_all("<F1>", lambda e: self._show_help())
        self.bind_all("<Button-3>", self._show_context_menu)

    def _trigger_next(self):
        self._nav_debounce.trigger(lambda: self.next_page())

    def _trigger_prev(self):
        self._nav_debounce.trigger(lambda: self.prev_page())

    def _trigger_space(self):
        self._nav_debounce.trigger(lambda: self._space_advance())

    def _execute_page_change(self, action):
        action()

    def _log_key_event(self, event) -> None:
        logging.info(
            "KeyPress keysym=%s char=%s keycode=%s state=%s widget=%s",
            event.keysym,
            repr(event.char),
            event.keycode,
            event.state,
            event.widget,
        )

    def _cancel_active_dialog(self) -> None:
        """Best-effort close of a Tk file dialog when quitting."""
        try:
            focus = self.tk.call("focus")
            if focus:
                toplevel = self.tk.call("winfo", "toplevel", focus)
                if toplevel and toplevel != str(self):
                    logging.info("Closing focused dialog: %s", toplevel)
                    self.tk.call("destroy", toplevel)
                    return
            children = self.tk.call("winfo", "children", ".")
            for child in children:
                if child.startswith(".__tk_filedialog"):
                    logging.info("Closing file dialog: %s", child)
                    self.tk.call("destroy", child)
                    return
        except tk.TclError:
            return

    def _open_dialog(self):
        if self._dialog_active:
            return
        self._dialog_active = True
        logging.info("Open dialog requested.")
        cursor_was_hidden = self._cursor_hidden
        if cursor_was_hidden:
            self._set_cursor_hidden(False)
        path = None
        try:
            dialog = tk.Toplevel(self.master)
            dialog.title("Open Comic")
            _as_wm(dialog).transient(_as_wm(self.master))
            dialog.resizable(False, False)
            dialog.protocol("WM_DELETE_WINDOW", lambda: dialog.destroy())

            dialog.bind("<Escape>", lambda e: self._quit())
            dialog.bind("q", lambda e: self._quit())
            dialog.bind("Q", lambda e: self._quit())
            dialog.bind("x", lambda e: self._quit())

            from tkinter import ttk

            frame = ttk.Frame(dialog, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text="File:").grid(row=0, column=0, sticky=tk.W)
            entry_var: tk.StringVar = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=entry_var, width=50)
            entry.grid(row=0, column=1, sticky=tk.EW)

            def browse():
                file_path = filedialog.askopenfilename(
                    parent=dialog,
                    title="Open Comic",
                    filetypes=FILE_DIALOG_TYPES,
                )
                if file_path:
                    entry_var.set(file_path)

            def browse_multi():
                file_paths = filedialog.askopenfilenames(
                    parent=dialog,
                    title="Open Comic",
                    filetypes=FILE_DIALOG_TYPES,
                )
                if file_paths:
                    entry_var.set(file_paths[0])

            ttk.Button(frame, text="Browse...", command=browse).grid(row=0, column=2)

            button_frame = ttk.Frame(frame)
            button_frame.grid(row=1, column=0, columnspan=3, pady=10)

            result = {"path": ""}

            def on_ok():
                result["path"] = entry_var.get()
                dialog.destroy()

            def on_cancel():
                dialog.destroy()

            ttk.Button(button_frame, text="Open", command=on_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)

            dialog.grab_set()
            entry.focus_set()
            self.master.wait_window(dialog)

            path = result["path"]

            if not path:
                logging.info("Open dialog canceled by user.")
            else:
                logging.info("Open dialog selected: %s", path)
                self._open_comic(Path(path))
        finally:
            if cursor_was_hidden:
                self._set_cursor_hidden(True)
            self._dialog_active = False
        if self._pending_quit:
            self._pending_quit = False
            self._quit()
            return
        if not path:
            return
        self._request_focus()

    def _open_comic(self, path: Path):
        open_start = time.perf_counter()
        perf_log("open_comic_start", 0, f"path={path.name}")

        if self.source and self.source.cleanup:
            try:
                self.source.cleanup()
            except Exception as e:
                logging.warning("Cleanup failed: %s", e)

        self.source = None
        self._pil_cache.clear()
        self._image_cache.clear()
        self._current_pil = None
        self._tk_img = None
        self._current_index = 0
        self._scroll_offset = 0
        self._scaled_size = None
        self.comic_path = path

        try:
            logging.info("Opening comic: %s", path)
            load_start = time.perf_counter()
            self.source = load_comic(path)
            perf_log("load_comic", time.perf_counter() - load_start)
        except Exception as e:
            logging.exception("Failed to open comic: %s", path)
            messagebox.showerror("Could not open comic", str(e))
            self._request_focus()
            return

        self._update_title()
        perf_log("open_comic_total", time.perf_counter() - open_start)
        # Don't render here - let Configure event trigger first render

    def _display_cached_image(self, img: Image.Image):
        self._current_pil = img

        imagetk_start = time.perf_counter()
        if self._imagetk_ready:
            try:
                self._tk_img = ImageTk.PhotoImage(img, master=self)
            except Exception:
                self._imagetk_ready = False
                self._tk_img = self._photoimage_from_pil(img)
        else:
            self._tk_img = self._photoimage_from_pil(img)
        perf_log("imagetk_conversion", time.perf_counter() - imagetk_start)

        canvas_start = time.perf_counter()
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())

        iw, ih = img.size
        self._scaled_size = (iw, ih)
        max_offset = max(0, ih - ch)
        if ih <= ch:
            self._scroll_offset = 0
        else:
            self._scroll_offset = min(max(self._scroll_offset, 0), max_offset)

        self.canvas.delete("all")
        self._canvas_image_id = None
        anchor = "center"
        x = cw // 2
        if ih <= ch:
            y = ch // 2
        else:
            anchor = "n"
            y = -self._scroll_offset
        self._canvas_image_id = self.canvas.create_image(x, y, image=self._tk_img, anchor=anchor)
        perf_log("canvas_update", time.perf_counter() - canvas_start)

    def _display_image_fast(self, img: Image.Image):
        """Display PIL image with fast NEAREST resampling for instant preview."""
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())

        iw, ih = img.size
        scale = min(cw / iw, ch / ih)
        if scale < 1:
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            img = img.resize((nw, nh), Image.Resampling.NEAREST)

        self._current_pil = img

        imagetk_start = time.perf_counter()
        if self._imagetk_ready:
            try:
                self._tk_img = ImageTk.PhotoImage(img, master=self)
            except Exception:
                self._imagetk_ready = False
                self._tk_img = self._photoimage_from_pil(img)
        else:
            self._tk_img = self._photoimage_from_pil(img)

        iw, ih = img.size
        self._scaled_size = (iw, ih)
        max_offset = max(0, ih - ch)
        if ih <= ch:
            self._scroll_offset = 0
        else:
            self._scroll_offset = min(max(self._scroll_offset, 0), max_offset)

        self.canvas.delete("all")
        self._canvas_image_id = None
        anchor = "center"
        x = cw // 2
        if ih <= ch:
            y = ch // 2
        else:
            anchor = "n"
            y = -self._scroll_offset
        self._canvas_image_id = self.canvas.create_image(x, y, image=self._tk_img, anchor=anchor)
        perf_log("display_fast_image", time.perf_counter() - imagetk_start)

    def _update_from_cache(self, index: int, img: Image.Image):
        logging.info("Update from cache: index=%d, current_index=%d", index, self._current_index)

        if not self.source:
            logging.warning("Update from cache: no source")
            return
        if index != self._current_index:
            logging.info("Update from cache: index mismatch, skipping")
            return

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())

        cache_key: tuple[int, int, int] | None = None
        # Only cache when canvas has proper dimensions to avoid caching tiny images
        if self._canvas_properly_sized:
            cache_key = (index, cw, ch)
        if cache_key is not None:
            self._image_cache[cache_key] = img
        logging.info("Update from cache: cached page %d at %dx%d", index, cw, ch)

        self._display_cached_image(img)
        self._first_proper_render_completed = True
        self._update_title()

    def _quit(self):
        if self._quitting:
            return
        if self._dialog_active:
            self._pending_quit = True
            logging.info("Quit requested during dialog; attempting to close dialog.")
            self._cancel_active_dialog()
            return
        self._quitting = True
        try:
            if self.source and self.source.cleanup:
                self.source.cleanup()
        finally:
            logging.info("Destroying app window.")
            self.master.destroy()

    def _minimize(self) -> None:
        logging.info("Minimize requested.")
        try:
            _as_wm(self.master).iconify()
        except tk.TclError:
            pass

    def _show_help(self) -> None:
        logging.info("Help dialog requested.")
        messagebox.showinfo(
            "cdisplayagain help",
            "Use arrow keys, Page Up/Down, or mouse wheel to navigate. W toggles fullscreen. Esc quits.",
        )

    def _dismiss_info(self) -> None:
        if self._info_overlay:
            self._info_overlay.destroy()
            self._info_overlay = None

    def _build_context_menu(self) -> tk.Menu:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Load files", command=self._open_dialog)
        menu.add_command(label="Minimize", command=self._minimize)
        menu.add_command(label="Quit", command=self._quit)
        return menu

    def _show_context_menu(self, event) -> None:
        logging.info("Context menu requested at %s,%s.", event.x_root, event.y_root)
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _bind_mouse(self) -> None:
        self.bind_all("<ButtonPress>", self._log_mouse_event, add=True)
        self.bind_all("<ButtonRelease>", self._log_mouse_event, add=True)
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._drag_pan)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        # Bind for Linux scrolling (if needed, though MouseWheel usually covers modern Tk)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)

    def _log_mouse_event(self, event) -> None:
        logging.info(
            "Mouse event type=%s num=%s delta=%s x=%s y=%s state=%s widget=%s",
            event.type,
            getattr(event, "num", None),
            getattr(event, "delta", None),
            event.x,
            event.y,
            event.state,
            event.widget,
        )

    def _start_pan(self, event) -> None:
        logging.info("Pan start y=%s.", event.y)
        self._drag_start_y = event.y

    def _drag_pan(self, event) -> None:
        if not hasattr(self, "_drag_start_y"):
            return
        logging.info("Pan drag y=%s.", event.y)
        delta = self._drag_start_y - event.y
        self._drag_start_y = event.y
        self._scroll_by(delta)

    def _on_mouse_wheel(self, event) -> None:
        logging.info("Mouse wheel delta=%s num=%s.", event.delta, getattr(event, "num", None))
        if hasattr(event, "num") and event.num:
            direction = -1 if event.num == 4 else 1
        elif event.delta == 0:
            return
        else:
            direction = -1 if event.delta > 0 else 1
        if self._scaled_size and self._scaled_size[1] > self.canvas.winfo_height():
            self._scroll_by(direction * self._scroll_step())
        else:
            if direction > 0:
                self.next_page()
            else:
                self.prev_page()

    def _on_canvas_configure(self, event):
        cw = event.width
        ch = event.height
        if cw >= 100 and ch >= 100:
            if not self._canvas_properly_sized:
                self._canvas_properly_sized = True
                self._first_render_done = True
                logging.info("Canvas properly sized: %dx%d, doing first sync render", cw, ch)
                self._render_current_sync()
            else:
                logging.info("Canvas resized: %dx%d", cw, ch)

    def _update_title(self):
        wm = _as_wm(self.master)
        if not self.source:
            wm.title(f"cdisplayagain - {self.comic_path.name}")
            return
        total = len(self.source.pages)
        wm.title(f"cdisplayagain - {self.comic_path.name} ({self._current_index + 1}/{total})")

    def _find_next_image_index(self, start_index: int) -> int | None:
        if not self.source:
            return None
        for index in range(start_index + 1, len(self.source.pages)):
            if not is_text_name(self.source.pages[index]):
                return index
        return None

    def _render_current(self):
        if not self.source:
            self.canvas.delete("all")
            self._canvas_image_id = None
            return

        name = self.source.pages[self._current_index]
        if is_text_name(name):
            self._render_info_with_image(name)
            self._update_title()
            return
        self._dismiss_info()

        index = self._current_index
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        cache_key = (index, cw, ch)

        logging.info("Rendering page %d at %dx%d", index, cw, ch)

        cached = self._image_cache.get(cache_key)
        if cached:
            logging.info("Cache hit for page %d", index)
            self._display_cached_image(cached)
            self._update_title()
        else:
            logging.info("Cache miss for page %d, requesting worker", index)
            self._worker.request_page(
                index, cw, ch, preload=False, render_generation=self._render_generation
            )
            self._update_title()

        next_idx = self._find_next_image_index(index)
        if next_idx is not None:
            logging.info("Preloading next image page %d", next_idx)
            self._worker.preload(next_idx)

    def _render_current_sync(self):
        if not self.source:
            return

        render_start = time.perf_counter()
        name = self.source.pages[self._current_index]
        if is_text_name(name):
            self._render_info_with_image(name)
            self._update_title()
            perf_log("render_current_sync", time.perf_counter() - render_start, "info_page")
            return
        self._dismiss_info()

        index = self._current_index
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        cache_key = (index, cw, ch)

        logging.info("Rendering page %d at %dx%d (sync)", index, cw, ch)

        cached = self._image_cache.get(cache_key)
        if cached:
            logging.info("Cache hit for page %d", index)
            self._display_cached_image(cached)
            self._update_title()
            self._first_proper_render_completed = True
            perf_log("render_current_sync", time.perf_counter() - render_start, "cache_hit")
            return

        if not self._first_proper_render_completed:
            logging.info("First proper render, skipping preview, requesting high-quality resize")
            self._worker.request_page(
                index, cw, ch, preload=False, render_generation=self._render_generation
            )
            self._update_title()
            perf_log("render_current_sync", time.perf_counter() - render_start, "first_render")
            return

        logging.info("Cache miss for page %d, displaying preview then requesting resize", index)
        raw_start = time.perf_counter()
        raw = self.source.get_bytes(self.source.pages[index])
        perf_log("get_bytes", time.perf_counter() - raw_start)

        decode_start = time.perf_counter()
        raw_img = Image.open(io.BytesIO(raw))
        perf_log("pil_decode_preview", time.perf_counter() - decode_start)

        display_start = time.perf_counter()
        self._display_image_fast(raw_img)
        self._update_title()
        perf_log("display_preview", time.perf_counter() - display_start)

        logging.info("Requesting high-quality resize for page %d", index)
        self._worker.request_page(
            index, cw, ch, preload=False, render_generation=self._render_generation
        )
        self._update_title()

        perf_log("render_current_sync", time.perf_counter() - render_start, "preview")

    def _render_info_with_image(self, name: str) -> None:
        image_index = self._find_next_image_index(self._current_index)
        if image_index is None:
            self.canvas.delete("all")
            self._canvas_image_id = None
            self._current_pil = None
            self._scaled_size = None
            self._scroll_offset = 0
            self._show_info_overlay(name)
            return

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        cache_key = (image_index, cw, ch)

        cached = self._image_cache.get(cache_key)
        if cached:
            self._display_cached_image(cached)
            self._show_info_overlay(name)
            return

        self._worker.request_page(
            image_index, cw, ch, preload=False, render_generation=self._render_generation
        )
        self._show_info_overlay(name)

    def _show_info_overlay(self, name: str) -> None:
        if not self.source:
            return
        if self._info_overlay:
            return
        try:
            text = self.source.get_bytes(name).decode("utf-8", errors="replace")
        except Exception:
            text = name
        overlay = tk.Label(
            self.canvas,
            text=text,
            bg="#111111",
            fg="#dddddd",
            justify="left",
            anchor="nw",
        )
        overlay.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)
        self._info_overlay = overlay

    def winfo_children(self):
        """Return widget children, omitting internal menus."""
        children = super().winfo_children()
        return [child for child in children if not isinstance(child, tk.Menu)]

    def _scroll_step(self) -> int:
        return max(50, self.canvas.winfo_height() // 5)

    def _scroll_by(self, delta: int):
        if not self._scaled_size:
            return
        logging.info("Scroll by delta=%s.", delta)
        ch = max(1, self.canvas.winfo_height())
        max_offset = max(0, self._scaled_size[1] - ch)
        if max_offset == 0:
            return
        new_offset = min(max_offset, max(0, self._scroll_offset + delta))
        if new_offset == self._scroll_offset:
            return
        self._scroll_offset = new_offset
        self._reposition_current_image()

    def _space_advance(self):
        logging.info("Space advance requested.")
        if self._info_overlay:
            self._dismiss_info()
            self.next_page()
            return
        if not self._scaled_size:
            self.next_page()
            return
        ch = max(1, self.canvas.winfo_height())
        max_offset = max(0, self._scaled_size[1] - ch)
        if max_offset == 0:
            self.next_page()
            return
        step = ch
        if self._scroll_offset >= max_offset:
            self.next_page()
            return
        if self._scroll_offset + step >= max_offset:
            self._scroll_offset = max_offset
            self._reposition_current_image()
            return
        self._scroll_by(step)

    def _scroll_down(self):
        logging.info("Scroll down requested.")
        self._scroll_by(self._scroll_step())

    def _scroll_up(self):
        logging.info("Scroll up requested.")
        self._scroll_by(-self._scroll_step())

    def _reposition_current_image(self):
        if not self._canvas_image_id or not self._scaled_size:
            return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        if self._scaled_size[1] <= ch:
            anchor = "center"
            y = ch // 2
        else:
            anchor = "n"
            # Clamp again in case canvas height changed out from under us
            max_offset = max(0, self._scaled_size[1] - ch)
            self._scroll_offset = min(max(self._scroll_offset, 0), max_offset)
            y = -self._scroll_offset
        self.canvas.itemconfigure(self._canvas_image_id, anchor=anchor)
        self.canvas.coords(self._canvas_image_id, cw // 2, y)

    def next_page(self):
        """Advance to the next page if available."""
        logging.info("Next page requested.")
        if not self.source:
            return
        if self._current_index < len(self.source.pages) - 1:
            self._current_index += 1
            self._scroll_offset = 0
            self._render_generation += 1
            self._render_current()

    def prev_page(self):
        """Move to the previous page if available."""
        logging.info("Prev page requested.")
        if not self.source:
            return
        if self._current_index > 0:
            self._current_index -= 1
            self._scroll_offset = 0
            self._render_generation += 1
            self._render_current()

    def first_page(self):
        """Jump to the first page in the source."""
        logging.info("First page requested.")
        if not self.source:
            return
        self._current_index = 0
        self._scroll_offset = 0
        self._render_generation += 1
        self._render_current()

    def last_page(self):
        """Jump to the last page in the source."""
        logging.info("Last page requested.")
        if not self.source:
            return
        self._current_index = len(self.source.pages) - 1
        self._scroll_offset = 0
        self._render_generation += 1
        self._render_current()

    def set_one_page_mode(self) -> None:
        """Provide placeholder for single-page mode parity."""
        return None

    def set_two_page_mode(self) -> None:
        """Provide placeholder for two-page mode parity."""
        return None

    def toggle_color_balance(self) -> None:
        """Provide placeholder for color balance toggle parity."""
        return None

    def toggle_yellow_reduction(self) -> None:
        """Provide placeholder for yellow reduction toggle parity."""
        return None

    def _show_hint_popup(self) -> None:
        return None

    def toggle_two_pages(self) -> None:
        """Provide placeholder for two-page toggle parity."""
        return None

    def toggle_hints(self) -> None:
        """Provide placeholder for hint toggle parity."""
        return None

    def toggle_two_page_advance(self) -> None:
        """Provide placeholder for two-page advance toggle parity."""
        return None

    def set_page_buffer(self, _: int | None = None) -> None:
        """Provide placeholder for page buffer setting parity."""
        return None

    def set_background_color(self, _: str | None = None) -> None:
        """Provide placeholder for background color setting parity."""
        return None

    def set_small_cursor(self) -> None:
        """Restore cursor visibility after hiding."""
        self._set_cursor_hidden(False)

    def set_mouse_binding(self, _: str | None = None) -> None:
        """Provide placeholder for mouse binding selection parity."""
        return None


def main():
    """Parse arguments and launch the comic viewer."""
    _init_logging()
    parser = argparse.ArgumentParser(description="Simple CBZ/CBR viewer (cdisplay-ish)")
    parser.add_argument("comic", nargs="?", help="Path to .cbz/.cbr, directory, or image file")
    args = parser.parse_args()

    # Create Tk root once
    root = tk.Tk()
    root.withdraw()

    path: Path | None = None
    if args.comic:
        path = Path(args.comic).expanduser()
    else:
        # Use the existing root for the dialog
        selection = filedialog.askopenfilename(
            parent=root, title="Open Comic", filetypes=FILE_DIALOG_TYPES
        )
        if not selection:
            root.destroy()
            return
        path = Path(selection)

    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        root.destroy()
        sys.exit(1)

    if "cbr" in path.suffix:
        require_pyvips()
    # Set initial full screen state BEFORE creating viewer
    # to ensure first render uses correct canvas dimensions
    root.attributes("-fullscreen", True)

    app = ComicViewer(root, path)
    app._fullscreen = True
    app._set_cursor_hidden(True)
    app._request_focus()

    root.deiconify()
    root.mainloop()


def require_pyvips():
    """Raise SystemExit if pyvips or libvips runtime dependencies are missing."""
    try:
        import pyvips

        if pyvips:
            return
    except ModuleNotFoundError as e:
        raise SystemExit(
            "pyvips is not installed.\n\n"
            "Fix:\n"
            "  uv pip install 'pyvips[binary]'   # macOS\n"
            "  # or on Linux:\n"
            "  sudo apt-get install -y libvips && uv pip install pyvips\n"
        ) from e
    except OSError as e:
        msg = str(e)
        if "libvips" in msg and ("dylib" in msg or "dlopen" in msg):
            raise SystemExit(
                "libvips could not be loaded.\n\n"
                "Fix options:\n"
                "  1) Recommended on macOS:\n"
                "     uv pip install 'pyvips[binary]'\n"
                "  2) Or use Homebrew vips and export the path before running:\n"
                "     brew install vips\n"
                "     export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib\n"
            ) from e
        raise


if __name__ == "__main__":
    main()
