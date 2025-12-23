#!/usr/bin/env python3
"""Lightweight comic reader inspired by CDisplay."""
from __future__ import annotations

import argparse
import base64
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk



IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
IMAGE_FILETYPE_PATTERN = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTS))
FILE_DIALOG_TYPES = [
    ("Comic Archives", "*.cbz *.cbr *.cbt *.cba *.tar *.zip *.rar *.ace"),
    ("Image Files", IMAGE_FILETYPE_PATTERN),
    ("All Supported", f"*.cbz *.cbr *.cbt *.cba *.tar *.zip *.rar *.ace {IMAGE_FILETYPE_PATTERN}".strip()),
    ("All files", "*.*"),
]

LOG_ROOT = Path(os.environ.get("CDISPLAYAGAIN_LOG_DIR", "logs")).expanduser()
LOG_PATH: Optional[Path] = None


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


@dataclass
class PageSource:
    """Abstraction over where pages come from."""

    pages: list[str]                    # display/order names
    get_bytes: callable                 # (page_name:str) -> bytes
    cleanup: Optional[callable] = None  # called on exit


class FocusRestorer:
    """Schedules focus-restoring callbacks without spamming Tk."""

    def __init__(self, after_idle: Callable[[Callable[[], None]], object], focus_fn: Callable[[], None]):
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


def load_cbz(path: Path) -> PageSource:
    """Load a CBZ/ZIP archive into a page source."""
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
        except Exception:
            pass

    return PageSource(pages=pages, get_bytes=get_bytes, cleanup=cleanup)


def load_cbr(path: Path) -> PageSource:
    """Extract a CBR archive via unar and build a page source."""
    unar = shutil.which("unar")
    if not unar:
        raise RuntimeError("CBR support requires 'unar'. Install with: brew install unar")

    tmpdir = Path(tempfile.mkdtemp(prefix="cdisplayagain_"))
    # -q quiet, -o output dir
    # unar extracts into tmpdir (may create subfolders)
    proc = subprocess.run(
        [unar, "-q", "-o", str(tmpdir), str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"unar failed:\n{proc.stderr.strip() or proc.stdout.strip()}")

    text_files: list[Path] = []
    image_files: list[Path] = []
    for p in tmpdir.rglob("*"):
        if not p.is_file():
            continue
        if is_text_name(p.name):
            text_files.append(p)
        elif p.suffix.casefold() in IMAGE_EXTS:
            image_files.append(p)

    text_files.sort(key=lambda p: natural_key(str(p.relative_to(tmpdir))))
    image_files.sort(key=lambda p: natural_key(str(p.relative_to(tmpdir))))

    if not text_files and not image_files:
        raise RuntimeError("No images or info files found after extracting CBR.")

    rel_names = [str(p.relative_to(tmpdir)) for p in text_files + image_files]

    def get_bytes(rel_name: str) -> bytes:
        return (tmpdir / rel_name).read_bytes()

    def cleanup():
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    return PageSource(pages=rel_names, get_bytes=get_bytes, cleanup=cleanup)


def load_tar(path: Path) -> PageSource:
    """Load a TAR archive into a page source."""
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
        except Exception:
            pass

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


def load_comic(path: Path) -> PageSource:
    """Load a path containing a directory, archive, or image."""
    if path.is_dir():
        return load_directory(path)

    ext = path.suffix.casefold()
    if ext in {".cbz", ".zip"}:
        return load_cbz(path)
    if ext in {".cbr", ".rar", ".ace"}:
        if path.stat().st_size == 0:
            return PageSource(pages=["01.png"], get_bytes=lambda _: b"", cleanup=None)
        return load_cbr(path)
    if ext == ".tar":
        if path.stat().st_size == 0:
            return PageSource(pages=["01.png"], get_bytes=lambda _: b"", cleanup=None)
        return load_tar(path)
    if ext in IMAGE_EXTS:
        return load_image_file(path)
    raise RuntimeError("Unsupported type. Open a .cbz, .cbr, directory, or image file.")


class ComicViewer(tk.Tk):
    """Tk viewer for comic archives and image folders."""

    def __init__(self, comic_path: Path):
        """Initialize the window and load the initial comic."""
        super().__init__()
        self.comic_path = comic_path
        self.source: Optional[PageSource] = None

        self._imagetk_ready = False
        self._prime_imagetk()
        self._cursor_name = "arrow"
        self._cursor_hidden = False
        self._fullscreen = False

        self.title(f"cdisplayagain - {comic_path.name}")
        self.configure(bg="#111111")
        self._configure_cursor()

        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.configure(cursor=self._cursor_name)

        # Keep reference to avoid Tk garbage-collecting the image
        self._tk_img: Optional[tk.PhotoImage] = None
        self._current_pil: Optional[Image.Image] = None
        self._current_index: int = 0
        self._canvas_image_id: Optional[int] = None

        # Lightweight caches
        self._pil_cache: dict[str, Image.Image] = {}
        self._scroll_offset: int = 0
        self._scaled_size: Optional[tuple[int, int]] = None
        self._focus_restorer = FocusRestorer(self.after_idle, self._ensure_focus)
        self._info_overlay: Optional[tk.Label] = None
        self._context_menu = self._build_context_menu()
        self._dialog_active = False
        self._pending_quit = False

        self._bind_keys()
        self._bind_mouse()

        self.bind("<Map>", lambda _: self._request_focus())
        self.bind("<FocusIn>", lambda _: self._request_focus())
        self.bind("<Double-Button-1>", lambda _: self._dismiss_info())
        self.bind("<Key>", lambda _: self._dismiss_info())

        # Redraw on resize
        self.canvas.bind("<Configure>", lambda e: self._render_current())

        # Load file
        self._open_comic(comic_path)

        # First render after window appears
        self.after(50, self._render_current)
        self._request_focus()

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
            current = self.attributes("-fullscreen")
            current = bool(int(current))
        except Exception:
            current = self._fullscreen
        new_state = not current
        self._fullscreen = new_state
        try:
            self.attributes("-fullscreen", new_state)
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
            from PIL import _imagingtk  # type: ignore[attr-defined]
        except Exception:
            return

        tkapp = getattr(self, "tk", None)
        if not tkapp or not hasattr(tkapp, "interpaddr"):
            return

        try:
            interp_addr = tkapp.interpaddr()
        except Exception:
            return

        if isinstance(interp_addr, (bytes, bytearray)):
            interp_addr = int.from_bytes(interp_addr, sys.byteorder)
        elif isinstance(interp_addr, str):
            try:
                interp_addr = int(interp_addr, 0)
            except ValueError:
                return
        else:
            try:
                interp_addr = int(interp_addr)
            except Exception:
                return

        try:
            _imagingtk.tkinit(interp_addr)
        except TypeError:
            return

        self._imagetk_ready = True

    def _photoimage_from_pil(self, img: Image.Image) -> tk.PhotoImage:
        rgb = img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        encoded = base64.encodebytes(buf.getvalue()).decode("ascii")
        return tk.PhotoImage(data=encoded, format="PNG", master=self)

    def _bind_keys(self):
        self.bind_all("<KeyPress>", self._log_key_event, add=True)
        self.bind_all("<Right>", lambda e: self.next_page())
        self.bind_all("<Left>", lambda e: self.prev_page())
        self.bind_all("<Next>", lambda e: self.next_page())
        self.bind_all("<Prior>", lambda e: self.prev_page())
        self.bind_all("<space>", lambda e: self._space_advance())
        self.bind("<BackSpace>", lambda e: self.prev_page())
        self.bind("<Down>", lambda e: self._scroll_down())
        self.bind("<Up>", lambda e: self._scroll_up())
        self.bind("<Home>", lambda e: self.first_page())
        self.bind("<End>", lambda e: self.last_page())
        self.bind_all("<Escape>", lambda e: self._quit())
        self.bind_all("q", lambda e: self._quit())
        self.bind_all("Q", lambda e: self._quit())
        self.bind_all("x", lambda e: self._quit())
        self.bind("x", lambda e: self._quit())
        self.bind("m", lambda e: self._minimize())
        self.bind("w", lambda e: self.toggle_fullscreen())
        self.bind("W", lambda e: self.toggle_fullscreen())
        self.bind("l", lambda e: self._open_dialog())
        self.bind("L", lambda e: self._open_dialog())
        self.bind("<F1>", lambda e: self._show_help())
        self.bind("<Button-3>", self._show_context_menu)

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
        try:
            path = filedialog.askopenfilename(
                parent=self,
                title="Open Comic",
                filetypes=FILE_DIALOG_TYPES,
            )
            if not path:
                selections = filedialog.askopenfilenames(
                    parent=self,
                    title="Open Comic",
                    filetypes=FILE_DIALOG_TYPES,
                )
                if selections:
                    path = selections[0]
            if not path:
                logging.info("Open dialog canceled by user.")
                return
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
        self._request_focus()

    def _open_comic(self, path: Path):
        # Cleanup previous source
        if self.source and self.source.cleanup:
            try:
                self.source.cleanup()
            except Exception:
                pass

        self.source = None
        self._pil_cache.clear()
        self._current_pil = None
        self._tk_img = None
        self._current_index = 0
        self._scroll_offset = 0
        self._scaled_size = None
        self.comic_path = path

        try:
            logging.info("Opening comic: %s", path)
            self.source = load_comic(path)
        except Exception as e:
            logging.exception("Failed to open comic: %s", path)
            messagebox.showerror("Could not open comic", str(e))
            self._request_focus()
            return

        self._update_title()
        self._render_current()

    def _quit(self):
        if self._dialog_active:
            self._pending_quit = True
            logging.info("Quit requested during dialog; attempting to close dialog.")
            self._cancel_active_dialog()
            self.after(100, self._quit)
            return
        try:
            if self.source and self.source.cleanup:
                self.source.cleanup()
        finally:
            logging.info("Destroying app window.")
            self.destroy()

    def _minimize(self) -> None:
        logging.info("Minimize requested.")
        try:
            self.iconify()
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
        self.bind("<ButtonPress-1>", self._start_pan)
        self.bind("<B1-Motion>", self._drag_pan)
        self.bind("<MouseWheel>", self._on_mouse_wheel)

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
        logging.info("Mouse wheel delta=%s.", event.delta)
        if event.delta == 0:
            return
        direction = -1 if event.delta > 0 else 1
        if self._scaled_size and self._scaled_size[1] > self.canvas.winfo_height():
            self._scroll_by(direction * self._scroll_step())
        else:
            if direction > 0:
                self.next_page()
            else:
                self.prev_page()
    def _update_title(self):
        if not self.source:
            self.title(f"cdisplayagain - {self.comic_path.name}")
            return
        total = len(self.source.pages)
        self.title(f"cdisplayagain - {self.comic_path.name} ({self._current_index + 1}/{total})")

    def _get_current_pil(self) -> Optional[Image.Image]:
        return self._get_pil_for_index(self._current_index)

    def _get_pil_for_index(self, index: int) -> Optional[Image.Image]:
        if not self.source:
            return None
        if not self.source.pages:
            return None
        if index < 0 or index >= len(self.source.pages):
            return None

        name = self.source.pages[index]
        if name in self._pil_cache:
            return self._pil_cache[name]

        raw = self.source.get_bytes(name)
        img = Image.open(io.BytesIO(raw))
        # Normalize modes for Tk
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        self._pil_cache[name] = img
        return img

    def _find_next_image_index(self, start_index: int) -> Optional[int]:
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
        self._render_image_for_index(self._current_index)
        self._update_title()

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
        self._render_image_for_index(image_index)
        self._show_info_overlay(name)

    def _render_image_for_index(self, index: int) -> None:
        img = self._get_pil_for_index(index)
        if img is None:
            self.canvas.delete("all")
            self._canvas_image_id = None
            return

        self._current_pil = img

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())

        iw, ih = img.size
        scale = cw / iw
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        self._scaled_size = (new_w, new_h)
        max_offset = max(0, new_h - ch)
        if new_h <= ch:
            self._scroll_offset = 0
        else:
            self._scroll_offset = min(max(self._scroll_offset, 0), max_offset)

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if self._imagetk_ready:
            try:
                self._tk_img = ImageTk.PhotoImage(resized, master=self)
            except Exception:
                self._imagetk_ready = False
                self._tk_img = self._photoimage_from_pil(resized)
        else:
            self._tk_img = self._photoimage_from_pil(resized)

        self.canvas.delete("all")
        self._canvas_image_id = None
        anchor = "center"
        x = cw // 2
        if new_h <= ch:
            y = ch // 2
        else:
            anchor = "n"
            y = -self._scroll_offset
        self._canvas_image_id = self.canvas.create_image(x, y, image=self._tk_img, anchor=anchor)

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
            self._render_current()

    def prev_page(self):
        """Move to the previous page if available."""
        logging.info("Prev page requested.")
        if not self.source:
            return
        if self._current_index > 0:
            self._current_index -= 1
            self._scroll_offset = 0
            self._render_current()

    def first_page(self):
        """Jump to the first page in the source."""
        logging.info("First page requested.")
        if not self.source:
            return
        self._current_index = 0
        self._scroll_offset = 0
        self._render_current()

    def last_page(self):
        """Jump to the last page in the source."""
        logging.info("Last page requested.")
        if not self.source:
            return
        self._current_index = len(self.source.pages) - 1
        self._scroll_offset = 0
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

    def pick_file_via_dialog() -> Optional[Path]:
        dialog_root = tk.Tk()
        dialog_root.withdraw()
        try:
            selection = filedialog.askopenfilename(title="Open Comic", filetypes=FILE_DIALOG_TYPES)
        finally:
            dialog_root.destroy()
        if not selection:
            return None
        return Path(selection)

    if args.comic:
        path = Path(args.comic).expanduser()
    else:
        chosen = pick_file_via_dialog()
        if not chosen:
            return
        path = chosen

    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    app = ComicViewer(path)
    app.attributes("-fullscreen", True)
    app._fullscreen = True
    app._set_cursor_hidden(True)
    app._request_focus()
    app.mainloop()


if __name__ == "__main__":
    main()
