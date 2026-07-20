"""Test-only image fixture builders -- real raster images for exercising ocr.py without needing
external binary fixture files on disk."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def build_image_with_text(lines: list[str], image_format: str = "PNG") -> bytes:
    """A real image, rendered with a legible font, whose visible text reads back as `lines`."""
    width, line_height = 700, 40
    image = Image.new("RGB", (width, line_height * (len(lines) + 1)), color="white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    for index, line in enumerate(lines):
        draw.text((10, 10 + index * line_height), line, fill="black", font=font)

    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


CORRUPTED_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"this claims to be a PNG but has no valid chunk data"
