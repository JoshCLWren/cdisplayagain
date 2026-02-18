"""Archive loading and page source abstractions."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PERF_LOGGING = os.environ.get("CDISPLAYAGAIN_PERF") == "1"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
ARCHIVE_EXTS = {".cbz", ".cbr", ".cba", ".cbt", ".zip", ".rar", ".ace", ".tar"}
IMAGE_FILETYPE_PATTERN = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTS))


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

    pages: list[str]  # display/order names
    get_bytes: Callable[[str], bytes]
    cleanup: Callable[[], None] | None = None  # called on exit


def get_sibling_comics(path: Path) -> tuple[list[Path], int]:
    """Scan the parent directory for archive files, sorted naturally.

    Returns a tuple of (sorted_archive_paths, index_of_path_in_list).
    Returns ([], -1) if path is not an archive, has no parent, or on error.
    """
    if path.suffix.casefold() not in ARCHIVE_EXTS:
        return ([], -1)
    if not path.parent.exists() or path.parent == path:
        return ([], -1)
    try:
        entries = list(path.parent.iterdir())
    except OSError:
        return ([], -1)
    siblings = sorted(
        [p for p in entries if p.is_file() and p.suffix.casefold() in ARCHIVE_EXTS],
        key=lambda p: natural_key(str(p.name)),
    )
    resolved = path.resolve()
    resolved_list = [p.resolve() for p in siblings]
    if resolved in resolved_list:
        index = resolved_list.index(resolved)
    else:
        return (siblings, -1)
    return (siblings, index)


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

    local_readers = threading.local()
    readers_lock = threading.Lock()
    readers: list[zipfile.ZipFile] = [zf]
    local_readers.zf = zf
    owner_thread = threading.get_ident()

    def _reader() -> zipfile.ZipFile:
        reader = getattr(local_readers, "zf", None)
        if reader is None:
            reader = zipfile.ZipFile(path, "r")
            local_readers.zf = reader
            with readers_lock:
                readers.append(reader)
        return reader

    def get_bytes(name: str) -> bytes:
        if threading.get_ident() == owner_thread:
            return zf.read(name)
        return _reader().read(name)

    def cleanup():
        with readers_lock:
            to_close = list(readers)
            readers.clear()
        for reader in to_close:
            try:
                reader.close()
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
