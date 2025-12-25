"""Image processing backend using pyvips for fast operations."""

import functools
from typing import Any

import pyvips
from PIL import Image


@functools.lru_cache(maxsize=32)
def get_resized_pil(raw_bytes: bytes, target_width: int, target_height: int) -> Image.Image:
    """Resize image bytes using pyvips and return PIL Image.

    Note: pyvips has incomplete type stubs, so we use Any here.
    The operations are safe as they match the actual pyvips API.
    """
    img: Any = pyvips.Image.new_from_buffer(raw_bytes, "")
    orig_w = img.width

    scale = target_width / orig_w

    resized: Any = img.resize(scale, kernel="lanczos3")
    jpeg_bytes = resized.write_to_buffer(".jpg[Q=75]")
    return Image.open(functools.__builtins__["__import__"]("io").BytesIO(jpeg_bytes))
