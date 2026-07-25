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
    """Load a CBZ/ZIP archive into a page source.

    Reads member names lazily without decompressing file contents. Actual
    decompression happens on-demand via get_bytes().
    """
    import zipfile

    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as e:
        raise RuntimeError(
            f"Failed to open CBZ: {path.name}. The file may be corrupt, "
            f"incomplete, or not a valid ZIP archive."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to open CBZ: {path.name}. Check that the file exists "
            f"and is readable."
        ) from e

    names = [n for n in zf.namelist() if not n.endswith("/")]
    text_names = [n for n in names if is_text_name(n)]
    image_names = [n for n in names if is_image_name(n)]
    text_names.sort(key=natural_key)
    image_names.sort(key=natural_key)
    pages = text_names + image_names

    if not pages:
        zf.close()
        raise RuntimeError(
            f"No images or info files found inside CBZ. "
            f"Checked {len(names)} members."
        )

    read_lock = threading.Lock()

    def get_bytes(name: str) -> bytes:
        with read_lock:
            try:
                return zf.read(name)
            except zipfile.BadZipFile as e:
                raise RuntimeError(
                    f"Failed to read page {name} from CBZ. The archive may be corrupt."
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Failed to read page {name}. Check disk space and file permissions."
                ) from e

    def cleanup():
        try:
            zf.close()
        except Exception as e:
            logging.warning("Cleanup failed: %s", e)

    return PageSource(pages=pages, get_bytes=get_bytes, cleanup=cleanup)


def load_cbr(path: Path) -> PageSource:
    """Extract a CBR archive via unrar2-cffi and build a page source.

    Filters to image/text members before decompression to avoid decompressing
    unrelated files. Extraction is lazy - bytes are decompressed on-demand via
    get_bytes() with in-memory caching to avoid repeated solid-RAR rescans.
    """
    from unrar.cffi import rarfile as rarfile_cffi

    tmpdir = Path(tempfile.mkdtemp(prefix="cdisplayagain_"))
    try:
        rar = rarfile_cffi.RarFile(str(path))
        with PerfTimer("load_cbr"):
            filenames = rar.namelist()

            text_file_names = [n for n in filenames if is_text_name(n)]
            image_file_names = [n for n in filenames if is_image_name(n)]

            text_file_names.sort(key=natural_key)
            image_file_names.sort(key=natural_key)
            all_file_names = text_file_names + image_file_names

            if not all_file_names:
                raise RuntimeError(
                    f"No images or info files found in CBR. "
                    f"Checked {len(filenames)} members."
                )

            extracted_cache: dict[str, bytes] = {}

            def get_bytes(rel_name: str) -> bytes:
                if rel_name in extracted_cache:
                    return extracted_cache[rel_name]
                try:
                    data = rar.read(rel_name)
                except Exception as e:
                    logging.error("Failed to decompress %s from CBR: %s", rel_name, e)
                    raise RuntimeError(
                        f"Failed to decompress page: {rel_name}. "
                        f"The archive may be corrupted, encrypted, or use an unsupported RAR feature."
                    ) from e
                extracted_cache[rel_name] = data
                return data

            def cleanup():
                try:
                    shutil.rmtree(tmpdir)
                except Exception as e:
                    logging.warning("Cleanup failed: %s", e)

            return PageSource(pages=all_file_names, get_bytes=get_bytes, cleanup=cleanup)
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
