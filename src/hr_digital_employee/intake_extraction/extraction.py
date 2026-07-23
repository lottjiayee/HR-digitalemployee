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


_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.\w+")

# Mirrors profile_adapter.py's/red_flags.py's own _YEAR_RANGE_PATTERN (each module keeps its own
# copy deliberately -- see ASSUMPTIONS.md's "duplicated year-range regex" entry). A standalone
# tenure line like "2019 - 2023" under a job title or degree is a common, legitimate resume
# layout that also happens to satisfy _is_phone_like_line's digit/separator check (8 digits, only
# "-"/space chars) -- confirmed this silently deleted the only date signal for a job entry,
# zeroing out years_of_experience for an otherwise fully-qualified candidate. Two bare years in the
# 1900s/2000s joined by a dash is unambiguously a date range, never a phone number, regardless of
# digit count.
_YEAR_RANGE_LINE_PATTERN = re.compile(
    r"^\s*(?:19|20)\d{2}\s*-\s*(?:(?:19|20)\d{2}|present|current)\s*$", re.IGNORECASE
)

_ISO_DATE_LINE_PATTERN = re.compile(r"^\s*(?:19|20)\d{2}-\d{2}-\d{2}\s*$")
"""A bare ISO-format date (e.g. a job's start date, "2023-01-15") has >=7 digits and consists only
of digits/dashes -- exactly what _is_phone_like_line's heuristic looks for -- so without this
exemption it was silently deleted as if it were a phone number, the same "consistency guarantee"
failure class as the year-range exemption above, just not fully closed by it (a single date has no
second year to make the existing YYYY-YYYY pattern match)."""


def _is_phone_like_line(line: str) -> bool:
    stripped = line.strip().rstrip(".")
    if _YEAR_RANGE_LINE_PATTERN.match(stripped) or _ISO_DATE_LINE_PATTERN.match(stripped):
        return False
    digit_count = sum(char.isdigit() for char in stripped)
    if digit_count < 7:
        return False
    return all(char.isdigit() or char in "+()-. " for char in stripped)


def _is_contact_info_line(line: str) -> bool:
    return bool(_EMAIL_PATTERN.search(line)) or _is_phone_like_line(line)


def _drop_contact_info_lines(section_text: str) -> str:
    """Drops any email/phone-shaped line from a section's captured text -- a resume whose own
    contact block sits at the very end of the document (a real, if less common, layout) has no
    closing header of its own, so it gets silently absorbed into whichever section comes last (see
    ASSUMPTIONS.md). An email or phone number is never legitimate Skills/Experience/Education
    content, so filtering these two specific, high-precision patterns out is safe regardless of
    where in a section they land -- unlike a bare name or city, which isn't reliably
    distinguishable from real content and is left alone."""
    lines = [line for line in section_text.splitlines() if not _is_contact_info_line(line)]
    return "\n".join(lines).strip()


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
        sections[name] = _drop_contact_info_lines(text[content_start:end].strip())
    return sections


_CATEGORY_LABEL_SEPARATOR = re.compile("[:：]")
"""Matches the ASCII colon or its full-width Chinese equivalent "：" -- standard Chinese
typography for a category label (e.g. "编程语言：C++，Python，Java") uses the full-width form, not
the ASCII one. ASCII-only matching left every Chinese skills line's label glued to its first
skill, the identical bug already fixed for the English case, just not ported to Chinese
punctuation (see ASSUMPTIONS.md's bilingual-consistency requirement)."""


def _strip_category_label(line: str) -> str:
    """Drops a leading category label from a skills line (e.g. "Programming Languages: C++,
    Python" -> " C++, Python") -- otherwise the label stays glued to the first split skill
    ("Programming Languages: C++") instead of being recognized as a header for the list, not part
    of any one skill. A resume skills line uses a colon this way almost exclusively for category
    labels, never as part of an actual skill name, so everything up to the first colon is dropped
    whenever one is present."""
    match = _CATEGORY_LABEL_SEPARATOR.search(line)
    return line[match.end() :] if match else line


def _confidence_for(section_text: str, ocr_confidence: float | None) -> float:
    """Length is still a floor signal (a one-character match is less trustworthy than a full
    paragraph), but it's no longer the only one: `ocr_confidence` -- Tesseract's own average
    per-word recognition confidence, when this text came from OCR rather than a PDF text layer or
    plain-text passthrough (see pdf_text.py/ocr.py) -- caps it. Without this, a section header
    Tesseract happened to recognize correctly, followed by unreadable garbled content, scored
    exactly as confidently "VERIFIED" as clean text (confirmed via a real resume template: a
    "WORK EXPERIENCE" section of OCR gibberish still scored 0.95/meets-must-have-confidence,
    because the heuristic only ever checked whether the section was "long enough"). `None` means
    no OCR was involved -- the length heuristic alone applies, unchanged from before."""
    if not section_text:
        return 0.0
    length_based = 0.95 if len(section_text) >= 10 else 0.5
    if ocr_confidence is None:
        return length_based
    return min(length_based, ocr_confidence)


class ExtractionService:
    """Parses raw resume text into the four structured pillars with per-field confidence."""

    def extract(self, raw_text: str, ocr_confidence: float | None = None) -> ExtractedResume:
        sections = _split_sections(raw_text)

        return ExtractedResume(
            skills=self._extract_skills_field(sections.get("skills", ""), ocr_confidence),
            projects=self._extract_list_field(sections.get("projects", ""), ocr_confidence),
            experience=self._extract_text_field(sections.get("experience", ""), ocr_confidence),
            education=self._extract_text_field(sections.get("education", ""), ocr_confidence),
            parser_version=PARSER_VERSION,
        )

    def _extract_list_field(
        self, section_text: str, ocr_confidence: float | None
    ) -> ExtractedField[list[str]]:
        if not section_text:
            return ExtractedField(value=None, confidence=0.0, status=FieldStatus.UNVERIFIED)
        items = [line.strip("-• \t") for line in section_text.splitlines() if line.strip()]
        return ExtractedField(
            value=items,
            confidence=_confidence_for(section_text, ocr_confidence),
            status=FieldStatus.VERIFIED,
        )

    def _extract_skills_field(
        self, section_text: str, ocr_confidence: float | None
    ) -> ExtractedField[list[str]]:
        # Skills are also split on commas, not just newlines, unlike _extract_list_field's other
        # caller (projects): a real downloaded resume was found scoring 0% on every mandatory
        # skill despite listing them, because a single comma-separated line (e.g. "C, Java, SQL,
        # Linux") was kept as one unsplit list item -- no exact skill-name match is possible
        # against a whole line. Projects deliberately do NOT get this treatment: a project bullet
        # routinely contains commas within its own prose (e.g. "Led a team of 5, delivering 2
        # weeks early"), and splitting on every comma there would fragment one project into
        # several meaningless fragments. The split also recognizes the full-width Chinese comma
        # "，" (standard Chinese typography, e.g. "C++，Python，Java") -- ASCII-only splitting
        # reproduced this exact 0%-score bug for Chinese resumes.
        if not section_text:
            return ExtractedField(value=None, confidence=0.0, status=FieldStatus.UNVERIFIED)
        items = [
            piece.strip("-• \t")
            for line in section_text.splitlines()
            for piece in re.split("[,，]", _strip_category_label(line))
            if piece.strip("-• \t")
        ]
        return ExtractedField(
            value=items,
            confidence=_confidence_for(section_text, ocr_confidence),
            status=FieldStatus.VERIFIED,
        )

    def _extract_text_field(
        self, section_text: str, ocr_confidence: float | None
    ) -> ExtractedField[str]:
        if not section_text:
            return ExtractedField(value=None, confidence=0.0, status=FieldStatus.UNVERIFIED)
        return ExtractedField(
            value=section_text,
            confidence=_confidence_for(section_text, ocr_confidence),
            status=FieldStatus.VERIFIED,
        )
