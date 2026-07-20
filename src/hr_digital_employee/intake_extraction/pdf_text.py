"""PDF byte-to-text extraction (SOP 2.1, module-1 design.md §3.2 Extraction Service).

Resolves the "build vs. buy" open decision (design.md §10.6, ASSUMPTIONS.md) on the build side:
pypdf's text layer extraction, feeding the existing heuristic section-header splitter in
extraction.py. This module only turns bytes into text -- it does not attempt OCR, so a
scanned/image-only PDF has no extractable text layer and is treated the same as a corrupted or
encrypted file: unparseable, routed to manual review (FR-4).
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

PDF_MAGIC_BYTES = b"%PDF-"


def extract_text(file_bytes: bytes) -> str | None:
    """Return the PDF's text layer, or None if it cannot be read.

    Bytes that don't start with the PDF header are passed through as already-plain-text --
    this keeps non-PDF test fixtures and any future plain-text channel adapter working without
    wrapping every input in a real PDF container.
    """
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        return file_bytes.decode("utf-8", errors="replace")

    try:
        reader = PdfReader(BytesIO(file_bytes))
        if reader.is_encrypted:
            return None
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PyPdfError:
        return None

    return text if text.strip() else None
