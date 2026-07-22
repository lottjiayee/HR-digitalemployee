"""Test-only image fixture builders -- real raster images for exercising ocr.py without needing
external binary fixture files on disk."""

from __future__ import annotations

import struct
import zlib
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


def build_decompression_bomb_png_bytes() -> bytes:
    """A well-formed PNG header declaring absurd dimensions (60000x60000) but almost no actual
    pixel data -- reproduces a decompression-bomb submission cheaply (no multi-gigabyte buffer is
    ever built; `Image.new()`/a real Pillow-rendered image can't be used to test this at all, since
    constructing one this size would itself exhaust memory). Built with raw PNG chunks rather than
    Pillow because Pillow's own encoder would perform the same size check this fixture exists to
    trigger."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    width = height = 60_000
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + b"\x00" * (width * 3))  # one scanline only, truncated on purpose
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def build_sidebar_resume_image() -> bytes:
    """A synthetic two-column resume layout with small icon glyphs next to sidebar text --
    exercises OCR against a dense multi-column/icon layout, contrasted with
    `build_clean_layout_with_icon_row_image()`'s single-column counterpart (see ASSUMPTIONS.md's
    OCR accuracy tradeoff section)."""
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


def build_clean_layout_with_icon_row_image() -> bytes:
    """A single-column resume layout where small icon glyphs are confined to one contact-info
    row and the rest is plain paragraph text -- the contrasting, high-accuracy counterpart to
    `build_sidebar_resume_image()`'s dense multi-column icon layout. A real-world resume image
    with this shape (icons isolated to one line, body text in one clean column) was observed to
    OCR close to perfectly aside from that one icon row (see ASSUMPTIONS.md)."""
    width, height = 700, 260
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    for index in range(3):
        x = 20 + index * 220
        draw.ellipse([x, 15, x + 20, 35], fill="black")  # icon glyph, no text of its own
    contact_line = "(555) 123-4567 | jane.doe@example.com | San Jose, CA"
    draw.text((20, 45), contact_line, fill="black", font=font)

    body_lines = [
        "PROFESSIONAL EXPERIENCE",
        "Facility Property Manager | February 2017",
        "Silicon Valley Tech Park, San Jose, CA",
        "Manage preventive maintenance for corporate campuses",
    ]
    for index, line in enumerate(body_lines):
        draw.text((20, 90 + index * 40), line, fill="black", font=font)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
