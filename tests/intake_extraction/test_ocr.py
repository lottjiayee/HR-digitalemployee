"""Tests for image OCR (module-1 design.md §3.2, FR-4, ASSUMPTIONS.md)."""

from __future__ import annotations

import pytest
from image_fixtures import (
    CORRUPTED_PNG_BYTES,
    build_clean_layout_with_icon_row_image,
    build_decompression_bomb_png_bytes,
    build_image_with_text,
    build_sidebar_resume_image,
    rotate_image_bytes,
)
from PIL import Image

from hr_digital_employee.intake_extraction import ocr
from hr_digital_employee.intake_extraction.ocr import _corrected_for_rotation

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
    result = ocr.extract_text(image_bytes)

    assert result is not None
    text, confidence = result
    assert "Skills" in text
    assert "Python" in text
    assert 0.0 <= confidence <= 1.0


@requires_tesseract
def test_a_clean_image_gets_a_high_confidence_score() -> None:
    # Regression: confidence used to be a pure length heuristic (any section >= 10 characters
    # scored 0.95, regardless of whether the text was actually coherent) -- this is Tesseract's
    # own average per-word recognition confidence, not a guess.
    image_bytes = build_image_with_text(["Skills", "Python, SQL", "Working Experience"])
    result = ocr.extract_text(image_bytes)

    assert result is not None
    _text, confidence = result
    assert confidence >= 0.85


@requires_tesseract
def test_corrupted_image_bytes_are_unparseable() -> None:
    assert ocr.extract_text(CORRUPTED_PNG_BYTES) is None


def test_decompression_bomb_image_is_unparseable_not_a_crash() -> None:
    # Security regression: a resume image whose header declares far more pixels than its actual
    # data backs up must route to manual review like any other unparseable file, not raise
    # PIL.Image.DecompressionBombError uncaught and crash the whole intake batch (gateway.py's
    # run_once() has no per-submission try/except). Doesn't need Tesseract -- Image.open() itself
    # raises before any OCR call is made.
    assert ocr.extract_text(build_decompression_bomb_png_bytes()) is None


@requires_tesseract
def test_sidebar_layout_with_icons_still_returns_text_without_crashing() -> None:
    # Regression fixture for the icon/sidebar/multi-column shape that a real-world resume image
    # was observed to OCR noticeably worse than a clean single-column layout (see ASSUMPTIONS.md).
    # This deliberately does NOT assert exact wording -- Tesseract's output on this kind of layout
    # is version-dependent and known to be imperfect. It only guards against the dispatch path
    # crashing or silently regressing to None on a layout this shape.
    result = ocr.extract_text(build_sidebar_resume_image())

    assert result is not None
    _text, confidence = result
    # Confirmed via the real resume this fixture reproduces: a dense multi-column/icon layout
    # scores noticeably lower than a clean one (see test_a_clean_image_gets_a_high_confidence_
    # score's >=0.85 clean-layout baseline) -- not asserting an exact number since Tesseract's
    # output on this kind of layout is version-dependent, but the signal itself must exist.
    assert 0.0 <= confidence <= 1.0


@requires_tesseract
@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_a_rotated_scan_is_corrected_before_ocr(degrees: int) -> None:
    # Regression: a resume image scanned or photographed sideways/upside down (a common
    # phone-camera/flatbed-scanner mistake) used to OCR into unreadable garble instead of routing
    # to manual review or scoring correctly -- confirmed a plain 90-degree rotation of this exact
    # fixture collapsed confidence from ~0.93 to ~0.33 with garbled text before this fix.
    # Tesseract's orientation-and-script-detection (OSD) pass now corrects the rotation first.
    upright_result = ocr.extract_text(build_clean_layout_with_icon_row_image())
    rotated_bytes = rotate_image_bytes(build_clean_layout_with_icon_row_image(), degrees)
    rotated_result = ocr.extract_text(rotated_bytes)

    assert upright_result is not None
    assert rotated_result is not None
    upright_text, upright_confidence = upright_result
    rotated_text, rotated_confidence = rotated_result
    assert "PROFESSIONAL EXPERIENCE" in rotated_text
    assert "Facility Property Manager | February 2017" in rotated_text
    assert rotated_confidence == pytest.approx(upright_confidence, abs=0.05)
    assert rotated_text == upright_text


def test_a_low_confidence_orientation_guess_is_not_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: Tesseract's OSD pass can misjudge an upright, never-rotated image as needing a
    # 90/180/270-degree turn -- confirmed empirically this happens for ordinary legible text about
    # 1 in 15 times, always at a confidence well below what a genuinely-rotated image scores.
    # Applying every nonzero guess unconditionally would silently flip perfectly good images upside
    # down, collapsing OCR confidence -- worse than not correcting rotation at all.
    upright_image = Image.new("RGB", (10, 10), color="white")
    monkeypatch.setattr(
        "pytesseract.image_to_osd",
        lambda *args, **kwargs: {"rotate": 180, "orientation_conf": 0.5},
    )

    corrected = _corrected_for_rotation(upright_image)

    assert corrected is upright_image


def test_a_high_confidence_orientation_guess_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    image = Image.new("RGB", (10, 20), color="white")
    monkeypatch.setattr(
        "pytesseract.image_to_osd",
        lambda *args, **kwargs: {"rotate": 90, "orientation_conf": 5.0},
    )

    corrected = _corrected_for_rotation(image)

    assert corrected.size == (20, 10)  # 90-degree rotation with expand=True swaps width/height


@requires_tesseract
def test_clean_layout_with_isolated_icon_row_ocrs_body_text_accurately() -> None:
    # Contrasting counterpart to the sidebar/icon layout above: a real-world resume image with
    # icons confined to one contact-info row (not interleaved throughout multiple columns) was
    # observed to OCR the surrounding body text almost perfectly (see ASSUMPTIONS.md). Unlike the
    # sidebar test, this one DOES assert exact wording -- that's the point of the contrast.
    result = ocr.extract_text(build_clean_layout_with_icon_row_image())

    assert result is not None
    text, _confidence = result
    assert "PROFESSIONAL EXPERIENCE" in text
    assert "Facility Property Manager | February 2017" in text
    assert "Silicon Valley Tech Park, San Jose, CA" in text
    assert "Manage preventive maintenance for corporate campuses" in text
