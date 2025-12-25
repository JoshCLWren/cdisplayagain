"""Image processing backend using pyvips for fast operations."""

import functools
import importlib.util
import io

from PIL import Image

HAS_PYVIPS = importlib.util.find_spec("pyvips") is not None


@functools.lru_cache(maxsize=32)
def get_resized_bytes(raw_bytes: bytes, target_width: int, target_height: int) -> bytes:
    """Resize image bytes using pyvips (fast) or Pillow (fallback)."""
    if HAS_PYVIPS:
        return _resize_with_pyvips(raw_bytes, target_width, target_height)
    return _resize_with_pillow(raw_bytes, target_width, target_height)


def _resize_with_pyvips(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fast resize using libvips via pyvips."""
    import pyvips

    img = pyvips.Image.new_from_buffer(raw_bytes, "")
    orig_w = img.width

    scale = width / orig_w

    resized = img.resize(scale, kernel="lanczos3")
    return resized.write_to_buffer(".png")


def _resize_with_pillow(raw_bytes: bytes, width: int, height: int) -> bytes:
    """Fallback resize using Pillow."""
    img = Image.open(io.BytesIO(raw_bytes))
    orig_w, orig_h = img.size

    scale = width / orig_w
    new_h = max(1, int(orig_h * scale))

    resized = img.resize((width, new_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()
