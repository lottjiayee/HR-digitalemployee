"""Module 1 -> Module 2 profile adapter (ASSUMPTIONS.md: "CandidateProfile vs. Module 1's
ExtractedResume"). Turns Module 1's free-text/list extraction output into the typed,
already-resolved `CandidateProfile` the Scoring Engine consumes.

A regex-heuristic stub, same spirit as `intake_extraction/extraction.py`'s own section-header
heuristics -- see ASSUMPTIONS.md for exactly what it does and doesn't handle (no word-form numbers
like "five years", no "-Present" open-ended ranges, no NLP-based degree extraction).
"""

from __future__ import annotations

import re

from hr_digital_employee.intake_extraction.interfaces import (
    ExtractedField,
    ExtractedResume,
    FieldStatus,
)
from hr_digital_employee.scoring_engine.models import CandidateProfile, EducationLevel

_EXPLICIT_YEARS_PATTERN = re.compile(r"(\d{1,3})\+?\s*years?", re.IGNORECASE)
_YEAR_RANGE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})\b")
# The separator accepts the ASCII hyphen-minus plus the en dash (U+2013) and em dash (U+2014):
# word processors' AutoCorrect commonly convert a typed hyphen between two numbers into an en
# dash, and PDF exporters/resume templates routinely emit either dash form natively -- confirmed
# an identical "2015-2020" vs "2015–2020" employment range (same candidate, same everything
# else) produced 5.0 vs 0.0 years_of_experience purely from this typographic difference, a direct
# violation of the consistency guarantee (SOP 2.1.1: identical qualifications, same outcome
# regardless of format). Word-form ranges ("2015 to 2020") remain a separate, still-open gap (see
# module docstring).

_DEGREE_KEYWORDS: tuple[tuple[EducationLevel, re.Pattern[str]], ...] = (
    (
        EducationLevel.DOCTORATE,
        re.compile(r"\b(?:ph\.?d|doctorate|doctoral)\b|博士", re.IGNORECASE),
    ),
    (EducationLevel.MASTER, re.compile(r"\b(?:master|msc|m\.sc|mba)\b|硕士", re.IGNORECASE)),
    # Chinese "学士" (bachelor's degree) must not match inside "副学士" (associate degree) --
    # confirmed a Chinese-language resume stating an identical Bachelor's qualification as its
    # English equivalent ("Bachelor of Computer Science" / "计算机科学学士") scored
    # EducationLevel.NONE instead of BACHELOR, since every keyword here was English-only, a
    # consistency-guarantee violation (SOP 2.1.1) in the same class as the other Chinese-language
    # bugs fixed elsewhere in this codebase.
    (
        EducationLevel.BACHELOR,
        re.compile(r"\b(?:bachelor|bsc|b\.sc|bba|bs|ba)\b|(?<!副)学士", re.IGNORECASE),
    ),
    (
        EducationLevel.ASSOCIATE,
        re.compile(r"\bassociate'?s?\s+degree\b|副学士", re.IGNORECASE),
    ),
    (
        EducationLevel.HIGH_SCHOOL,
        re.compile(r"\b(?:high school|secondary school)\b|高中|中学", re.IGNORECASE),
    ),
)


def _years_of_experience(experience: ExtractedField[str]) -> float:
    if experience.status is not FieldStatus.VERIFIED or not experience.value:
        return 0.0
    text = experience.value

    explicit_matches = _EXPLICIT_YEARS_PATTERN.findall(text)
    if explicit_matches:
        # Prefer the largest number mentioned, not just the first -- a resume saying "8 years
        # total experience, including 3 years as a lead" should credit 8, not whichever came first.
        return float(max(int(m) for m in explicit_matches))

    # Fallback: no "N years" phrase -- sum each year range's own length (not the overall min-to-max
    # span, which would overcount a candidate with a career-break gap between two ranges). Ranges
    # are merged first so two overlapping/concurrent roles (e.g. a side contract during a full-time
    # job) don't double-count the overlapping years.
    ranges = [
        (int(start), int(end))
        for start, end in _YEAR_RANGE_PATTERN.findall(text)
        if int(end) >= int(start)
    ]
    if ranges:
        return float(sum(end - start for start, end in _merge_ranges(ranges)))

    return 0.0


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _education_level(education: ExtractedField[str]) -> EducationLevel:
    if education.status is not FieldStatus.VERIFIED or not education.value:
        return EducationLevel.NONE
    text = education.value
    for level, pattern in _DEGREE_KEYWORDS:
        if pattern.search(text):
            return level
    return EducationLevel.NONE


def build_candidate_profile(extracted: ExtractedResume) -> CandidateProfile:
    """Map Module 1's `ExtractedResume` onto the Scoring Engine's `CandidateProfile`."""
    skills = (
        tuple(extracted.skills.value)
        if extracted.skills.status is FieldStatus.VERIFIED and extracted.skills.value
        else ()
    )
    project_count = (
        len(extracted.projects.value)
        if extracted.projects.status is FieldStatus.VERIFIED and extracted.projects.value
        else 0
    )
    return CandidateProfile(
        skills=skills,
        years_of_experience=_years_of_experience(extracted.experience),
        education_level=_education_level(extracted.education),
        project_count=project_count,
    )
