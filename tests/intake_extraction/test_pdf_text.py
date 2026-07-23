"""Tests for PDF byte-to-text extraction (module-1 design.md §3.2, FR-4/T1.6/T1.7)."""

from __future__ import annotations

import pytest
from image_fixtures import build_image_with_text
from pdf_fixtures import (
    CORRUPTED_PDF_BYTES,
    build_blank_pdf,
    build_encrypted_pdf,
    build_multi_page_pdf_with_text,
    build_pdf_with_text,
)

from hr_digital_employee.intake_extraction import ocr
from hr_digital_employee.intake_extraction.pdf_text import extract_text


def test_empty_bytes_are_treated_as_empty_plain_text_not_a_crash() -> None:
    # A zero-byte upload/submission decodes as valid (if empty) UTF-8 -- it must be treated as
    # "confidently read, nothing extractable", not raise or be mistaken for genuinely unparseable
    # bytes. Downstream, the gateway correctly routes the resulting empty extraction to manual
    # review via the ordinary low-confidence-must-have path (see test_gateway.py).
    result = extract_text(b"")

    assert result == ("", 1.0)


def test_a_large_multi_page_pdf_is_extracted_without_crashing() -> None:
    # Regression-guard against a large/many-page submission crashing or hanging pdf_text.py --
    # confirmed a real 100-page, ~40-line-per-page PDF (~220KB) extracts correctly well within a
    # second; this only needs to prove no crash/hang, not benchmark exact timing.
    pages = [[f"Line {i} on page {page}" for i in range(40)] for page in range(100)]
    pdf_bytes = build_multi_page_pdf_with_text(pages)

    result = extract_text(pdf_bytes)

    assert result is not None
    text, confidence = result
    assert confidence == 1.0
    assert "Line 0 on page 0" in text
    assert "Line 39 on page 99" in text


def test_non_pdf_bytes_pass_through_as_plain_text() -> None:
    result = extract_text(b"Skills:\nPython\n")

    assert result is not None
    text, confidence = result
    assert text == "Skills:\nPython\n"
    assert confidence == 1.0


def test_real_pdf_text_layer_is_extracted() -> None:
    pdf_bytes = build_pdf_with_text(["Skills:", "Python, SQL"])
    result = extract_text(pdf_bytes)

    assert result is not None
    text, confidence = result
    assert "Skills:" in text
    assert "Python, SQL" in text
    assert confidence == 1.0


def test_multi_page_pdf_concatenates_every_pages_text_in_order() -> None:
    # Regression-guard: extract_text() joins `page.extract_text()` across every page in
    # `reader.pages`, not just the first -- build_pdf_with_text() above only ever produces a
    # single-page PDF, so nothing previously exercised the multi-page concatenation itself.
    pdf_bytes = build_multi_page_pdf_with_text(
        [["Skills:", "Python, SQL"], ["Working Experience:", "5 years at TechCorp"]]
    )
    result = extract_text(pdf_bytes)

    assert result is not None
    text, confidence = result
    assert confidence == 1.0
    for expected in ("Skills:", "Python, SQL", "Working Experience:", "5 years at TechCorp"):
        assert expected in text
    assert text.index("Python, SQL") < text.index("Working Experience:")


def test_image_only_pdf_with_no_text_layer_is_unparseable() -> None:
    assert extract_text(build_blank_pdf()) is None


def test_encrypted_pdf_is_unparseable() -> None:
    assert extract_text(build_encrypted_pdf()) is None


def test_corrupted_pdf_bytes_are_unparseable() -> None:
    assert extract_text(CORRUPTED_PDF_BYTES) is None


def test_non_pdf_binary_that_is_not_valid_text_is_unparseable() -> None:
    # A file that is neither a PDF nor a recognized image format, nor valid UTF-8 text, must not
    # be silently decoded into replacement-character garbage -- it should route to manual review.
    unrecognized_binary = b"\x00\x01\x02\x03\xff\xfe\x00\x01" * 4
    assert extract_text(unrecognized_binary) is None


@pytest.mark.skipif(
    not ocr.tesseract_available(),
    reason="Tesseract binary not found on this machine -- see ASSUMPTIONS.md",
)
def test_image_bytes_are_dispatched_to_ocr() -> None:
    image_bytes = build_image_with_text(["Skills", "Python, SQL"])
    result = extract_text(image_bytes)

    assert result is not None
    text, _confidence = result
    assert "Skills" in text
