"""Image-to-text OCR for standalone raster-image resume submissions (module-1 design.md §3.2).

Resolves the local/offline side of the OCR "build vs. buy" decision (design.md §10.6,
ASSUMPTIONS.md): Tesseract via `pytesseract`, run entirely on-machine with no account, API key, or
network call. This is deliberately narrower than full document OCR -- it does not rasterize
scanned/image-only PDFs (that remains unsupported per FR-4/test.md T1.6); it only reads text out of
a resume submitted directly as a JPEG/PNG/GIF/BMP/WEBP image file. See ASSUMPTIONS.md for the
accuracy tradeoff against a managed cloud document-intelligence API.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_GIF_MAGIC_PREFIXES = (b"GIF87a", b"GIF89a")
_BMP_MAGIC = b"BM"

_WINDOWS_FALLBACK_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)
"""The UB-Mannheim Windows installer (winget id UB-Mannheim.TesseractOCR) doesn't always land on
PATH in an already-open shell -- these are its standard install locations, tried only after a
plain PATH lookup fails."""


def is_image(file_bytes: bytes) -> bool:
    """True if `file_bytes` looks like a raster image format this module can OCR."""
    if file_bytes.startswith(_JPEG_MAGIC) or file_bytes.startswith(_PNG_MAGIC):
        return True
    if file_bytes.startswith(_GIF_MAGIC_PREFIXES) or file_bytes.startswith(_BMP_MAGIC):
        return True
    return file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WEBP"


def tesseract_available() -> bool:
    """True if the Tesseract binary can be found (PATH or the Windows fallback locations).

    Exposed so callers -- including tests -- can skip OCR-dependent work with a clear reason on a
    machine where the Tesseract binary isn't installed, rather than failing on every image. A pure
    query -- it never mutates `pytesseract`'s global config; `extract_text` configures the
    fallback path itself, at the point it actually needs it.
    """
    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        return _find_fallback_tesseract_path() is not None


def extract_text(file_bytes: bytes) -> str | None:
    """OCR an image's text content, or None if it can't be read (routes to manual review)."""
    try:
        image = Image.open(BytesIO(file_bytes))
    except UnidentifiedImageError:
        return None

    try:
        text = pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError:
        if not _use_fallback_tesseract_path():
            return None
        text = pytesseract.image_to_string(image)

    return text if text.strip() else None


def _find_fallback_tesseract_path() -> Path | None:
    return next((p for p in _WINDOWS_FALLBACK_TESSERACT_PATHS if p.exists()), None)


def _use_fallback_tesseract_path() -> bool:
    """Configure pytesseract to use a fallback install path, if one exists. Mutates global state
    -- called only from `extract_text`, at the point OCR is actually about to run."""
    candidate = _find_fallback_tesseract_path()
    if candidate is None:
        return False
    pytesseract.pytesseract.tesseract_cmd = str(candidate)
    return True
