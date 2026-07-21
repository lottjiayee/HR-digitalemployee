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

_EXPLICIT_YEARS_PATTERN = re.compile(r"(\d+)\+?\s*years?", re.IGNORECASE)
_YEAR_RANGE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*-\s*((?:19|20)\d{2})\b")

_DEGREE_KEYWORDS: tuple[tuple[EducationLevel, re.Pattern[str]], ...] = (
    (EducationLevel.DOCTORATE, re.compile(r"\b(?:ph\.?d|doctorate|doctoral)\b", re.IGNORECASE)),
    (EducationLevel.MASTER, re.compile(r"\b(?:master|msc|m\.sc|mba)\b", re.IGNORECASE)),
    (EducationLevel.BACHELOR, re.compile(r"\b(?:bachelor|bsc|b\.sc|bba|bs|ba)\b", re.IGNORECASE)),
    (EducationLevel.ASSOCIATE, re.compile(r"\bassociate'?s?\s+degree\b", re.IGNORECASE)),
    (
        EducationLevel.HIGH_SCHOOL,
        re.compile(r"\b(?:high school|secondary school)\b", re.IGNORECASE),
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
    # span, which would overcount a candidate with a career-break gap between two ranges).
    ranges = _YEAR_RANGE_PATTERN.findall(text)
    if ranges:
        return float(sum(max(int(end) - int(start), 0) for start, end in ranges))

    return 0.0


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
