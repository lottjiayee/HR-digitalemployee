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

_LINE_START = re.IGNORECASE | re.MULTILINE
_PREFIX_WORDS = r"(?:[A-Za-z]+[ \t]+){0,2}"
r"""Every header pattern below is anchored to `^`, with at most two ordinary words allowed before
the keyword (e.g. "Adult Care Experience" -- a real subheading template resumes use, covered by
tests/intake_extraction/test_extraction.py's real-world fixtures). Without an anchor at all, a
header word appearing as the *last* word of an ordinary prose line (e.g. a summary line ending
"...continuous learning and education") would satisfy `word + optional colon + newline` just as
validly as a real standalone header, stealing that section's one marker slot before the real header
is ever reached (see ASSUMPTIONS.md). This bounded-prefix heuristic isn't foolproof -- a short,
unpunctuated prose fragment ending in a keyword within two words could still misfire -- but it
closes the demonstrated failure mode (an arbitrary-length sentence) while keeping the subheading
case working. Prefix words are joined with `[ \t]`, not `\s`, so they can't bleed backward across a
line break and swallow the *previous* line's content as if it were a two-word prefix."""

_BILINGUAL_SEP = r"\s*[·/|]\s*"
"""Joins an English header keyword and its Chinese equivalent when a bilingual resume states both
on one line (e.g. "Skills · 技能"), common in Hong Kong resumes (SOP 2.1.1 requires validated
accuracy on "mixed Chinese-English text", not just English-only documents)."""


def _bilingual(english: str, chinese: str) -> str:
    # Each side is wrapped in its own group before combining -- otherwise a `|` inside either
    # argument (e.g. education's "学历|教育(?:背景|经[历验])?") would break out of the intended
    # grouping and silently swallow the optional bilingual suffix on the wrong branch.
    english_group, chinese_group = rf"(?:{english})", rf"(?:{chinese})"
    return (
        rf"(?:{english_group}(?:{_BILINGUAL_SEP}{chinese_group})?"
        rf"|{chinese_group}(?:{_BILINGUAL_SEP}{english_group})?)"
    )


_SKILLS_CORE = _bilingual(_PREFIX_WORDS + "skills?", r"(?:专业)?技能")
_PROJECTS_CORE = _bilingual(_PREFIX_WORDS + "projects?", r"项目(?:经[历验])?")
_EXPERIENCE_CORE = _bilingual(
    _PREFIX_WORDS + r"(?:(?:work(?:ing)?\s+)?experience|work\s+history|employment\s+history)",
    r"(?:工作|从业)?经[历验]",
)
_EDUCATION_CORE = _bilingual(_PREFIX_WORDS + "education", r"学历|教育(?:背景|经[历验])?")
# Each header's bilingual "core" is built as a plain variable above, not inlined into the f-strings
# below -- a backslash inside an f-string's `{...}` expression isn't valid syntax before Python
# 3.12 (this project targets 3.11 at runtime), so the pattern pieces (which contain `\s`, `\n`
# etc.) can't be constructed directly inside the `rf"...{...}..."` interpolation itself.
_SECTION_HEADERS: dict[str, re.Pattern[str]] = {
    "skills": re.compile(rf"^\s*{_SKILLS_CORE}\s*[:：]?\s*\n", _LINE_START),
    "projects": re.compile(rf"^\s*{_PROJECTS_CORE}\s*[:：]?\s*\n", _LINE_START),
    "experience": re.compile(rf"^\s*{_EXPERIENCE_CORE}\s*[:：]?\s*\n", _LINE_START),
    "education": re.compile(rf"^\s*{_EDUCATION_CORE}\s*[:：]?\s*\n", _LINE_START),
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
