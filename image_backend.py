"""Image processing backend using pyvips for fast operations."""

import functools
import io
import threading

import pyvips
from PIL import Image

_vips_lock = threading.Lock()


@functools.lru_cache(maxsize=32)
def get_resized_pil(raw_bytes: bytes, target_width: int, target_height: int) -> Image.Image:
    """Resize image bytes using pyvips and return PIL Image."""
    with _vips_lock:
        img: pyvips.Image = pyvips.Image.new_from_buffer(raw_bytes, "")
        orig_w = int(img.width)

        scale = target_width / orig_w

        resized: pyvips.Image = img.resize(scale, kernel="lanczos3")
        jpeg_bytes = resized.write_to_buffer(".jpg[Q=75]")

    with Image.open(io.BytesIO(jpeg_bytes)) as pil_img:
        pil_img.load()
        return pil_img.copy()
