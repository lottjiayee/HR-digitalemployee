"""Red-flag detection (design.md §3.5, FR-12; module-3 doc §4).

Flags reviewed against Module 4's fairness mitigations: employment-gap and job-change-frequency
flags carry `neutral_framing=True` and are worded as interview-clarification prompts, never an
accusation or automatic penalty (test.md T3.6, module-3 doc §4) -- inconsistency and
keyword-stuffing are about resume-content integrity rather than personal circumstances, so they're
classified `neutral_framing=False`. All four descriptions still read as calm, professional
clarification requests; the distinction that matters is the flag classification consumers can act
on, not a deliberately harsher tone for the `False` cases.
"""

from __future__ import annotations

import re
from collections import Counter

from hr_digital_employee.ai_content.models import RedFlag, RedFlagKind
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume, FieldStatus

_YEAR_RANGE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*-\s*((?:19|20)\d{2})\b")

_MIN_GAP_YEARS = 1
"""A gap of at least this many years between consecutive roles is surfaced as a neutral
clarification item -- not assumed to mean anything on its own."""

_SHORT_TENURE_YEARS = 1
_FREQUENT_JOB_CHANGE_COUNT = 3
"""This many roles at or below `_SHORT_TENURE_YEARS` each is surfaced as a neutral clarification
item, not treated as a penalty."""

_KEYWORD_STUFFING_REPEAT_COUNT = 3


def _year_ranges(text: str) -> list[tuple[int, int]]:
    # A reversed range (e.g. a typo'd "2020-2015") is dropped rather than sorted in as-is -- letting
    # it through would fabricate/inflate an apparent gap around it (see ASSUMPTIONS.md).
    return sorted(
        (int(start), int(end))
        for start, end in _YEAR_RANGE_PATTERN.findall(text)
        if int(end) >= int(start)
    )


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Collapses overlapping/concurrent ranges (e.g. two roles held at the same time) into one,
    so `_detect_employment_gap` doesn't mistake the tail of a longer role for a gap next to a
    shorter, concurrent one. `ranges` must already be sorted (as `_year_ranges` returns)."""
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _detect_inconsistencies(text: str) -> tuple[RedFlag, ...]:
    # Every overlapping pair is reported, not just the first found -- two independent
    # inconsistencies in the same resume are two separate things worth asking about.
    ranges = _year_ranges(text)
    flags: list[RedFlag] = []
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            start_a, end_a = ranges[i]
            start_b, end_b = ranges[j]
            if start_a < end_b and start_b < end_a:  # overlapping date ranges
                flags.append(
                    RedFlag(
                        kind=RedFlagKind.INCONSISTENCY,
                        description=(
                            f"Overlapping dates found in work history ({start_a}-{end_a} and "
                            f"{start_b}-{end_b}) -- worth clarifying with the candidate."
                        ),
                        neutral_framing=False,
                    )
                )
    return tuple(flags)


def _detect_frequent_job_changes(text: str) -> RedFlag | None:
    ranges = _year_ranges(text)
    short_tenure_count = sum(1 for start, end in ranges if end - start <= _SHORT_TENURE_YEARS)
    if short_tenure_count >= _FREQUENT_JOB_CHANGE_COUNT:
        return RedFlag(
            kind=RedFlagKind.FREQUENT_JOB_CHANGES,
            description=(
                f"{short_tenure_count} roles of {_SHORT_TENURE_YEARS} year(s) or less each -- "
                "consider asking about the reasons for these transitions."
            ),
            neutral_framing=True,
        )
    return None


def _detect_employment_gaps(text: str) -> tuple[RedFlag, ...]:
    # Every gap between consecutive ranges is reported, not just the first -- a resume with two
    # separate unexplained gaps deserves two clarification prompts, not one.
    ranges = _merge_ranges(_year_ranges(text))
    flags: list[RedFlag] = []
    for (_start_earlier, end_earlier), (start_later, _end_later) in zip(
        ranges, ranges[1:], strict=False
    ):
        if start_later - end_earlier >= _MIN_GAP_YEARS:
            flags.append(
                RedFlag(
                    kind=RedFlagKind.EMPLOYMENT_GAP,
                    description=(
                        f"A gap between {end_earlier} and {start_later} isn't accounted for in "
                        "the listed work history -- consider asking about this period."
                    ),
                    neutral_framing=True,
                )
            )
    return tuple(flags)


def _detect_keyword_stuffing(extracted: ExtractedResume) -> RedFlag | None:
    if extracted.skills.status is not FieldStatus.VERIFIED or not extracted.skills.value:
        return None
    normalized = [skill.strip().lower() for skill in extracted.skills.value]
    repeated_skill, repeat_count = Counter(normalized).most_common(1)[0]
    if repeat_count >= _KEYWORD_STUFFING_REPEAT_COUNT:
        return RedFlag(
            kind=RedFlagKind.KEYWORD_STUFFING,
            description=(
                f'"{repeated_skill}" appears {repeat_count} times in the skills list -- worth '
                "checking whether this reflects genuine depth or keyword repetition."
            ),
            neutral_framing=False,
        )
    return None


def detect_red_flags(extracted: ExtractedResume) -> tuple[RedFlag, ...]:
    experience_text = (
        extracted.experience.value
        if extracted.experience.status is FieldStatus.VERIFIED and extracted.experience.value
        else ""
    )
    flags: list[RedFlag] = []
    flags.extend(_detect_inconsistencies(experience_text))
    frequent_job_changes_flag = _detect_frequent_job_changes(experience_text)
    if frequent_job_changes_flag is not None:
        flags.append(frequent_job_changes_flag)
    flags.extend(_detect_employment_gaps(experience_text))
    stuffing_flag = _detect_keyword_stuffing(extracted)
    if stuffing_flag is not None:
        flags.append(stuffing_flag)
    return tuple(flags)
