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
from typing import Any

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


def extract_text(file_bytes: bytes) -> tuple[str, float] | None:
    """OCR an image's text content, or None if it can't be read (routes to manual review).

    Returns `(text, confidence)`, where `confidence` is Tesseract's own average per-word
    recognition confidence (0-1) across every word it found -- not a length-based guess. This lets
    a caller distinguish clean OCR output from a dense/multi-column/icon-heavy layout Tesseract
    struggled with (confirmed via a real resume template: ~0.41 average confidence on a garbled
    two-column layout vs. ~0.95 on a clean single-column one) rather than trusting a "long enough
    to look plausible" heuristic on text that may be unreadable garbage (see ASSUMPTIONS.md).

    A submitted image is untrusted input (same threat model as injection_screening.py's text
    defenses): a PNG/etc. header can declare far more pixels than its actual data backs up, and
    Pillow raises `DecompressionBombError` for that rather than silently allocating a huge buffer.
    Treated the same as any other unparseable file, not left to crash the whole intake batch.

    A scanned resume fed in sideways or upside down (a common phone-camera/flatbed-scanner mistake)
    is corrected before the main recognition pass -- confirmed a plain 90-degree rotation turns
    otherwise-perfect OCR into unreadable garbage (~0.33 average word confidence vs. ~0.95 upright)
    without this. See `_corrected_for_rotation`.
    """
    try:
        image: Image.Image = Image.open(BytesIO(file_bytes))
    except (UnidentifiedImageError, Image.DecompressionBombError):
        return None

    try:
        image = _corrected_for_rotation(image)
        text = pytesseract.image_to_string(image)
        word_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        if not _use_fallback_tesseract_path():
            return None
        image = _corrected_for_rotation(image)
        text = pytesseract.image_to_string(image)
        word_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    if not text.strip():
        return None
    return text, _average_word_confidence(word_data)


def _corrected_for_rotation(image: Image.Image) -> Image.Image:
    """Detect and undo a 90/180/270-degree page rotation via Tesseract's orientation-and-
    script-detection (OSD) pass, so a resume scanned or photographed sideways doesn't OCR into
    garbage. OSD needs enough recognizable text to work at all -- on a sparse/small image it raises
    `TesseractError` ("Too few characters"), in which case the image is used as-is rather than
    treating a merely-too-sparse-for-OSD image as unparseable."""
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError:
        return image
    rotation = osd.get("rotate", 0)
    return image.rotate(-rotation, expand=True) if rotation else image


def _average_word_confidence(word_data: dict[str, list[Any]]) -> float:
    # Tesseract reports -1 for boxes that aren't recognized words (lines/paragraphs/blocks in the
    # same hierarchy `image_to_data` returns) -- only the >=0 entries are real per-word confidence
    # scores (0-100), which this averages and rescales to the 0-1 scale used everywhere else in
    # this codebase's confidence fields.
    scores = [int(value) for value in word_data["conf"] if int(value) >= 0]
    if not scores:
        return 0.0
    return (sum(scores) / len(scores)) / 100.0


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
