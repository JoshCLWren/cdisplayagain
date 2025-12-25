"""Create test comic files with scrambled/random images."""

import io
import random
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(exist_ok=True, parents=True)


def create_random_image(width, height):
    """Create a random image with noise."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for _ in range(1000):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.rectangle([x_min, y_min, x_max, y_max], fill=color)

    return img


def create_test_cbz(output_path, num_pages=25):
    """Create a CBZ file with random images (same size as Titans sample)."""
    width, height = 1934, 2952
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(num_pages):
            img = create_random_image(width, height)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            zf.writestr(f"page_{i + 1:05d}.jpg", buf.getvalue())


def create_test_cbr(output_path, num_pages=29):
    """Create a CBR file (as ZIP for compatibility with unrar2-cffi)."""
    width, height = 1074, 1650
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(num_pages):
            img = create_random_image(width, height)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            zf.writestr(f"image_{i + 1:03d}.jpg", buf.getvalue())


if __name__ == "__main__":
    cbz_path = FIXTURES_DIR / "test_cbz.cbz"
    cbr_path = FIXTURES_DIR / "test_cbr.cbr"

    create_test_cbz(cbz_path, num_pages=25)
    create_test_cbr(cbr_path, num_pages=29)

    print(f"Created test CBZ: {cbz_path}")
    print(f"Created test CBR: {cbr_path}")
