"""Raw submission byte-to-text extraction (SOP 2.1, module-1 design.md §3.2 Extraction Service).

Dispatches by format: a real PDF's text layer via pypdf; a standalone raster image (JPEG/PNG/
GIF/BMP/WEBP) via Tesseract OCR (ocr.py); anything else passed through as plain text. This module
does not rasterize a *scanned/image-only PDF* -- that has no extractable text layer and is treated
the same as a corrupted or encrypted file: unparseable, routed to manual review (FR-4/test.md T1.6).
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from hr_digital_employee.intake_extraction import ocr

PDF_MAGIC_BYTES = b"%PDF-"


_EXACT_TEXT_CONFIDENCE = 1.0
"""Confidence for text extracted deterministically -- a real PDF's text layer or a plain-text
passthrough -- as opposed to OCR's probabilistic per-word recognition. Not a judgement that the
resume's *content* is trustworthy, only that the bytes-to-text step itself introduced no
uncertainty of its own."""


def extract_text(file_bytes: bytes) -> tuple[str, float] | None:
    """Return `(text, confidence)`, or None if the submission cannot be read.

    `confidence` (0-1) reflects the bytes-to-text step's own reliability -- always
    `_EXACT_TEXT_CONFIDENCE` for a PDF's text layer or the plain-text fallback (exact, not a
    guess), or Tesseract's real average per-word OCR confidence for an image (see ocr.py). Module
    2's extraction confidence scoring uses this to avoid treating a garbled OCR result as
    trustworthy just because it happens to be long enough (see ASSUMPTIONS.md).

    Bytes that are neither a PDF nor a recognized image format are passed through as
    already-plain-text -- this keeps non-PDF test fixtures and any future plain-text channel
    adapter working without wrapping every input in a real PDF container. A strict UTF-8 decode
    is required for that fallback: an arbitrary unrecognized binary format is not valid UTF-8 and
    must be treated as unparseable (FR-4) rather than silently decoded into replacement-character
    garbage that would otherwise sail through extraction as an empty-but-accepted resume.
    """
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        if ocr.is_image(file_bytes):
            return ocr.extract_text(file_bytes)
        try:
            return file_bytes.decode("utf-8"), _EXACT_TEXT_CONFIDENCE
        except UnicodeDecodeError:
            return None

    try:
        reader = PdfReader(BytesIO(file_bytes))
        if reader.is_encrypted:
            return None
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PyPdfError:
        return None

    return (text, _EXACT_TEXT_CONFIDENCE) if text.strip() else None
