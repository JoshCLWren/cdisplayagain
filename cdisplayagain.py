#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk



IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
IMAGE_FILETYPE_PATTERN = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTS))
FILE_DIALOG_TYPES = [
    ("Comic Archives", "*.cbz *.cbr"),
    ("Image Files", IMAGE_FILETYPE_PATTERN),
    ("All Supported", f"*.cbz *.cbr {IMAGE_FILETYPE_PATTERN}".strip()),
    ("All files", "*.*"),
]


def natural_key(s: str):
    # Natural sort: "10" > "2" correctly
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", s)]


def is_image_name(name: str) -> bool:
    return Path(name).suffix.casefold() in IMAGE_EXTS


@dataclass
class PageSource:
    """Abstraction over where pages come from."""
    pages: list[str]                    # display/order names
    get_bytes: callable                 # (page_name:str) -> bytes
    cleanup: Optional[callable] = None  # called on exit


class FocusRestorer:
    """Schedules focus-restoring callbacks without spamming Tk."""

    def __init__(self, after_idle: Callable[[Callable[[], None]], object], focus_fn: Callable[[], None]):
        self._after_idle = after_idle
        self._focus_fn = focus_fn
        self._pending = False

    def schedule(self) -> None:
        if self._pending:
            return
        self._pending = True
        self._after_idle(self._run)

    def _run(self) -> None:
        self._pending = False
        self._focus_fn()


def load_cbz(path: Path) -> PageSource:
    zf = zipfile.ZipFile(path, "r")
    # Include images even if nested in directories inside the zip
    names = [n for n in zf.namelist() if not n.endswith("/") and is_image_name(n)]
    names.sort(key=natural_key)

    if not names:
        zf.close()
        raise RuntimeError("No images found inside CBZ.")

    def get_bytes(name: str) -> bytes:
        return zf.read(name)

    def cleanup():
        try:
            zf.close()
        except Exception:
            pass

    return PageSource(pages=names, get_bytes=get_bytes, cleanup=cleanup)


def load_cbr(path: Path) -> PageSource:
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

    files: list[Path] = []
    for p in tmpdir.rglob("*"):
        if p.is_file() and p.suffix.casefold() in IMAGE_EXTS:
            files.append(p)

    files.sort(key=lambda p: natural_key(str(p.relative_to(tmpdir))))

    if not files:
        raise RuntimeError("No images found after extracting CBR.")

    rel_names = [str(p.relative_to(tmpdir)) for p in files]

    def get_bytes(rel_name: str) -> bytes:
        return (tmpdir / rel_name).read_bytes()

    def cleanup():
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    return PageSource(pages=rel_names, get_bytes=get_bytes, cleanup=cleanup)


def load_directory(path: Path) -> PageSource:
    if not path.is_dir():
        raise RuntimeError("Provided path is not a directory")

    files = [p for p in path.rglob("*") if p.is_file() and is_image_name(p.name)]
    files.sort(key=lambda p: natural_key(str(p.relative_to(path))))

    if not files:
        raise RuntimeError("No images found in this directory.")

    rel_names = [str(p.relative_to(path)) for p in files]

    def get_bytes(rel_name: str) -> bytes:
        return (path / rel_name).read_bytes()

    return PageSource(pages=rel_names, get_bytes=get_bytes, cleanup=None)


def load_image_file(path: Path) -> PageSource:
    if not path.is_file() or not is_image_name(path.name):
        raise RuntimeError("Not an image file")

    name = path.name

    def get_bytes(_: str) -> bytes:
        return path.read_bytes()

    return PageSource(pages=[name], get_bytes=get_bytes, cleanup=None)


def load_comic(path: Path) -> PageSource:
    if path.is_dir():
        return load_directory(path)

    ext = path.suffix.casefold()
    if ext == ".cbz":
        return load_cbz(path)
    if ext == ".cbr":
        return load_cbr(path)
    if ext in IMAGE_EXTS:
        return load_image_file(path)
    raise RuntimeError("Unsupported type. Open a .cbz, .cbr, directory, or image file.")


class ComicViewer(tk.Tk):
    def __init__(self, comic_path: Path):
        super().__init__()
        self.comic_path = comic_path
        self.source: Optional[PageSource] = None

        self._imagetk_ready = False
        self._prime_imagetk()
        self._cursor_name = "arrow"

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

        self._build_menus()
        self._bind_keys()

        self.bind("<Map>", lambda _: self._request_focus())
        self.bind("<FocusIn>", lambda _: self._request_focus())

        # Redraw on resize
        self.canvas.bind("<Configure>", lambda e: self._render_current())

        # Load file
        self._open_comic(comic_path)

        # First render after window appears
        self.after(50, self._render_current)
        self._request_focus()

    def _request_focus(self) -> None:
        self._focus_restorer.schedule()

    def _configure_cursor(self) -> None:
        """Use a minimal cursor to mimic CDisplay's pointer."""
        for cursor_name in ("none", "dotbox", "arrow"):
            try:
                self.configure(cursor=cursor_name)
                self._cursor_name = cursor_name
                return
            except tk.TclError:
                continue

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

    def _build_menus(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open…", command=self._open_dialog, accelerator="Cmd+O")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._quit, accelerator="Cmd+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        nav_menu = tk.Menu(menubar, tearoff=0)
        nav_menu.add_command(label="Previous Page", command=self.prev_page)
        nav_menu.add_command(label="Next Page", command=self.next_page)
        nav_menu.add_separator()
        nav_menu.add_command(label="First Page", command=self.first_page)
        nav_menu.add_command(label="Last Page", command=self.last_page)
        menubar.add_cascade(label="Navigate", menu=nav_menu)

        self.config(menu=menubar)

        # macOS command keys
        self.bind_all("<Command-o>", lambda e: self._open_dialog())
        self.bind_all("<Command-q>", lambda e: self._quit())

    def _bind_keys(self):
        self.bind("<Right>", lambda e: self.next_page())
        self.bind("<Left>", lambda e: self.prev_page())
        self.bind("<space>", lambda e: self.next_page())
        self.bind("<BackSpace>", lambda e: self.prev_page())
        self.bind("<Down>", lambda e: self._scroll_down())
        self.bind("<Up>", lambda e: self._scroll_up())
        self.bind("<Home>", lambda e: self.first_page())
        self.bind("<End>", lambda e: self.last_page())
        self.bind("<Escape>", lambda e: self._quit())
        self.bind("q", lambda e: self._quit())
        self.bind("Q", lambda e: self._quit())
        self.bind("l", lambda e: self._open_dialog())
        self.bind("L", lambda e: self._open_dialog())

    def _open_dialog(self):
        path = filedialog.askopenfilename(title="Open Comic", filetypes=FILE_DIALOG_TYPES)
        if not path:
            self._request_focus()
            return
        self._open_comic(Path(path))
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
            self.source = load_comic(path)
        except Exception as e:
            messagebox.showerror("Could not open comic", str(e))
            self._request_focus()
            return

        self._update_title()
        self._render_current()

    def _quit(self):
        try:
            if self.source and self.source.cleanup:
                self.source.cleanup()
        finally:
            self.destroy()

    def _update_title(self):
        if not self.source:
            self.title(f"cdisplayagain - {self.comic_path.name}")
            return
        total = len(self.source.pages)
        self.title(f"cdisplayagain - {self.comic_path.name} ({self._current_index + 1}/{total})")

    def _get_current_pil(self) -> Optional[Image.Image]:
        if not self.source:
            return None
        if not self.source.pages:
            return None

        name = self.source.pages[self._current_index]
        if name in self._pil_cache:
            return self._pil_cache[name]

        raw = self.source.get_bytes(name)
        img = Image.open(io.BytesIO(raw))
        # Normalize modes for Tk
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        self._pil_cache[name] = img
        return img

    def _render_current(self):
        if not self.source:
            self.canvas.delete("all")
            self._canvas_image_id = None
            return

        img = self._get_current_pil()
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
                self._tk_img = ImageTk.PhotoImage(resized)
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

        self._update_title()

    def _scroll_step(self) -> int:
        return max(50, self.canvas.winfo_height() // 5)

    def _scroll_by(self, delta: int):
        if not self._scaled_size:
            return
        ch = max(1, self.canvas.winfo_height())
        max_offset = max(0, self._scaled_size[1] - ch)
        if max_offset == 0:
            return
        new_offset = min(max_offset, max(0, self._scroll_offset + delta))
        if new_offset == self._scroll_offset:
            return
        self._scroll_offset = new_offset
        self._reposition_current_image()

    def _scroll_down(self):
        self._scroll_by(self._scroll_step())

    def _scroll_up(self):
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
        if not self.source:
            return
        if self._current_index < len(self.source.pages) - 1:
            self._current_index += 1
            self._scroll_offset = 0
            self._render_current()

    def prev_page(self):
        if not self.source:
            return
        if self._current_index > 0:
            self._current_index -= 1
            self._scroll_offset = 0
            self._render_current()

    def first_page(self):
        if not self.source:
            return
        self._current_index = 0
        self._scroll_offset = 0
        self._render_current()

    def last_page(self):
        if not self.source:
            return
        self._current_index = len(self.source.pages) - 1
        self._scroll_offset = 0
        self._render_current()

def main():
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
    app._request_focus()
    app.mainloop()


if __name__ == "__main__":
    main()
