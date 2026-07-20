"""Structured extraction of the four resume pillars (SOP 2.1).

The real parsing approach (managed document-intelligence API vs. custom NLP) is an open decision
(md/progress.md §2a, design.md §10.6). This module ships a heuristic, section-header-based stub
extractor so the rest of the pipeline is fully testable end to end. See ASSUMPTIONS.md.
"""

from __future__ import annotations

import re

from hr_digital_employee.intake_extraction.models import (
    ExtractedField,
    ExtractedResume,
    FieldStatus,
)

PARSER_VERSION = "stub-0.1.0"

_SECTION_HEADERS: dict[str, re.Pattern[str]] = {
    "skills": re.compile(r"skills?\s*:?\s*\n", re.IGNORECASE),
    "projects": re.compile(r"projects?\s*:?\s*\n", re.IGNORECASE),
    "experience": re.compile(
        r"(?:(?:work(?:ing)?\s+)?experience|work\s+history|employment\s+history)\s*:?\s*\n",
        re.IGNORECASE,
    ),
    "education": re.compile(r"education\s*:?\s*\n", re.IGNORECASE),
}


def _split_sections(text: str) -> dict[str, str]:
    """Locate each section header and slice the text between consecutive header starts."""
    markers: list[tuple[int, int, str]] = []  # (header_start, content_start, name)
    for name, pattern in _SECTION_HEADERS.items():
        match = pattern.search(text)
        if match:
            markers.append((match.start(), match.end(), name))
    markers.sort(key=lambda marker: marker[0])

    sections: dict[str, str] = {}
    for index, (_header_start, content_start, name) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        sections[name] = text[content_start:end].strip()
    return sections


def _confidence_for(section_text: str) -> float:
    """Small heuristic: non-trivial content in a matched section scores high confidence."""
    if not section_text:
        return 0.0
    return 0.95 if len(section_text) >= 10 else 0.5


class ExtractionService:
    """Parses raw resume text into the four structured pillars with per-field confidence."""

    def extract(self, raw_text: str) -> ExtractedResume:
        sections = _split_sections(raw_text)

        return ExtractedResume(
            skills=self._extract_list_field(sections.get("skills", "")),
            projects=self._extract_list_field(sections.get("projects", "")),
            experience=self._extract_text_field(sections.get("experience", "")),
            education=self._extract_text_field(sections.get("education", "")),
            parser_version=PARSER_VERSION,
        )

    def _extract_list_field(self, section_text: str) -> ExtractedField[list[str]]:
        if not section_text:
            return ExtractedField(value=None, confidence=0.0, status=FieldStatus.UNVERIFIED)
        items = [line.strip("-• \t") for line in section_text.splitlines() if line.strip()]
        return ExtractedField(
            value=items,
            confidence=_confidence_for(section_text),
            status=FieldStatus.VERIFIED,
        )

    def _extract_text_field(self, section_text: str) -> ExtractedField[str]:
        if not section_text:
            return ExtractedField(value=None, confidence=0.0, status=FieldStatus.UNVERIFIED)
        return ExtractedField(
            value=section_text,
            confidence=_confidence_for(section_text),
            status=FieldStatus.VERIFIED,
        )
