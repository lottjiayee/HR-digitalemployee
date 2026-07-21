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


def build_sidebar_resume_image() -> bytes:
    """A synthetic two-column resume layout with small icon glyphs next to sidebar text --
    reproduces (without embedding a real downloaded file) the icon/sidebar/multi-column shape
    that a real-world resume image was observed to OCR noticeably worse than a clean single-column
    layout (see ASSUMPTIONS.md's OCR accuracy tradeoff section)."""
    width, height = 700, 320
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    draw.rectangle([0, 0, 200, height], fill=(230, 230, 230))
    for index, label in enumerate(["Contact", "Skills", "Languages"]):
        y = 20 + index * 60
        draw.ellipse([15, y, 35, y + 20], fill="black")  # icon glyph, no text of its own
        draw.text((45, y), label, fill="black", font=font)

    for index, line in enumerate(["Work History", "Entry-Level Position", "2023 - Present"]):
        draw.text((220, 20 + index * 40), line, fill="black", font=font)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
