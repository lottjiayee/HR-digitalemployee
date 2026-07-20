"""Tests for PDF byte-to-text extraction (module-1 design.md §3.2, FR-4/T1.6/T1.7)."""

from __future__ import annotations

from pdf_fixtures import (
    CORRUPTED_PDF_BYTES,
    build_blank_pdf,
    build_encrypted_pdf,
    build_pdf_with_text,
)

from hr_digital_employee.intake_extraction.pdf_text import extract_text


def test_non_pdf_bytes_pass_through_as_plain_text() -> None:
    assert extract_text(b"Skills:\nPython\n") == "Skills:\nPython\n"


def test_real_pdf_text_layer_is_extracted() -> None:
    pdf_bytes = build_pdf_with_text(["Skills:", "Python, SQL"])
    text = extract_text(pdf_bytes)

    assert text is not None
    assert "Skills:" in text
    assert "Python, SQL" in text


def test_image_only_pdf_with_no_text_layer_is_unparseable() -> None:
    assert extract_text(build_blank_pdf()) is None


def test_encrypted_pdf_is_unparseable() -> None:
    assert extract_text(build_encrypted_pdf()) is None


def test_corrupted_pdf_bytes_are_unparseable() -> None:
    assert extract_text(CORRUPTED_PDF_BYTES) is None
