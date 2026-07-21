"""Persistent, append-only record of the raw text each submission's extraction step produced
(module-1 design.md §3.2) -- whether that text came from a PDF's text layer, Tesseract OCR on an
image, or the plain-text fallback. Lets a human inspect exactly what extraction produced for a
given submission without re-running the pipeline.
"""

from __future__ import annotations

from pathlib import Path

from hr_digital_employee.intake_extraction.models import RawSubmission

_SEPARATOR = "=" * 72


class TextExtractionLog:
    """Appends each submission's extracted text to a single, ever-growing text file.

    A real deployment may want this in a database or object store instead, with retention rules
    for the PII it contains -- this stub keeps Module 1 independently testable and gives a
    human-readable trail on disk in the meantime. See ASSUMPTIONS.md.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, submission: RawSubmission, text: str) -> None:
        header = (
            f"{_SEPARATOR}\n"
            f"received_at={submission.received_at.isoformat()} "
            f"channel={submission.channel.value} "
            f"candidate={submission.display_identifier}\n"
            f"{_SEPARATOR}\n"
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(header)
            handle.write(text)
            handle.write("\n\n")
