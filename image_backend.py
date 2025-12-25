"""Image processing backend using pyvips for fast operations."""

import functools
import io
from typing import Optional

try:
    import pyvips

    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False

from PIL import Image


@functools.lru_cache(maxsize=32)
def get_resized_bytes(raw_bytes: bytes, target_width: int, target_height: int) -> bytes:
    """Resize image bytes using pyvips (fast) or Pillow (fallback)."""
    if HAS_PYVIPS:
        return _resize_with_pyvips(raw_bytes, target_width, target_height)
    return _resize_with_pillow(raw_bytes, target_width, target_height)


def _resize_with_pyvips(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fast resize using libvips via pyvips."""
    import pyvips  # type: ignore

    img = pyvips.Image.new_from_buffer(raw_bytes, "")
    orig_w = img.width
    orig_h = img.height

    scale_w = width / orig_w
    scale_h = height / orig_h
    scale = min(scale_w, scale_h)

    resized = img.resize(scale, kernel="lanczos3")
    return resized.write_to_buffer(".png")


def _resize_with_pillow(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fallback resize using Pillow."""
    img = Image.open(io.BytesIO(raw_bytes))
    resized = img.resize((width, height), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()
