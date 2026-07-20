"""Tests for image OCR (module-1 design.md §3.2, FR-4, ASSUMPTIONS.md)."""

from __future__ import annotations

import pytest
from image_fixtures import CORRUPTED_PNG_BYTES, build_image_with_text

from hr_digital_employee.intake_extraction import ocr

requires_tesseract = pytest.mark.skipif(
    not ocr.tesseract_available(),
    reason="Tesseract binary not found on this machine -- see ASSUMPTIONS.md",
)


def test_jpeg_bytes_are_recognized_as_image() -> None:
    assert ocr.is_image(build_image_with_text(["Skills"], image_format="JPEG")) is True


def test_png_bytes_are_recognized_as_image() -> None:
    assert ocr.is_image(build_image_with_text(["Skills"], image_format="PNG")) is True


def test_pdf_bytes_are_not_recognized_as_image() -> None:
    assert ocr.is_image(b"%PDF-1.4\n...") is False


def test_plain_text_bytes_are_not_recognized_as_image() -> None:
    assert ocr.is_image(b"Skills:\nPython\n") is False


@requires_tesseract
def test_real_image_text_is_ocrd() -> None:
    image_bytes = build_image_with_text(["Skills", "Python, SQL"])
    text = ocr.extract_text(image_bytes)

    assert text is not None
    assert "Skills" in text
    assert "Python" in text


@requires_tesseract
def test_corrupted_image_bytes_are_unparseable() -> None:
    assert ocr.extract_text(CORRUPTED_PNG_BYTES) is None
