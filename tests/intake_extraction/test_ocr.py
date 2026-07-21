"""Tests for image OCR (module-1 design.md §3.2, FR-4, ASSUMPTIONS.md)."""

from __future__ import annotations

import pytest
from image_fixtures import (
    CORRUPTED_PNG_BYTES,
    build_clean_layout_with_icon_row_image,
    build_image_with_text,
    build_sidebar_resume_image,
)

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


@requires_tesseract
def test_sidebar_layout_with_icons_still_returns_text_without_crashing() -> None:
    # Regression fixture for the icon/sidebar/multi-column shape that a real-world resume image
    # was observed to OCR noticeably worse than a clean single-column layout (see ASSUMPTIONS.md).
    # This deliberately does NOT assert exact wording -- Tesseract's output on this kind of layout
    # is version-dependent and known to be imperfect. It only guards against the dispatch path
    # crashing or silently regressing to None on a layout this shape.
    text = ocr.extract_text(build_sidebar_resume_image())

    assert text is not None


@requires_tesseract
def test_clean_layout_with_isolated_icon_row_ocrs_body_text_accurately() -> None:
    # Contrasting counterpart to the sidebar/icon layout above: a real-world resume image with
    # icons confined to one contact-info row (not interleaved throughout multiple columns) was
    # observed to OCR the surrounding body text almost perfectly (see ASSUMPTIONS.md). Unlike the
    # sidebar test, this one DOES assert exact wording -- that's the point of the contrast.
    text = ocr.extract_text(build_clean_layout_with_icon_row_image())

    assert text is not None
    assert "PROFESSIONAL EXPERIENCE" in text
    assert "Facility Property Manager | February 2017" in text
    assert "Silicon Valley Tech Park, San Jose, CA" in text
    assert "Manage preventive maintenance for corporate campuses" in text
