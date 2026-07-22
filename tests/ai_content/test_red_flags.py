"""Tests for red-flag detection (FR-12, test.md T3.4, T3.6)."""

from __future__ import annotations

from hr_digital_employee.ai_content.models import RedFlagKind
from hr_digital_employee.ai_content.red_flags import detect_red_flags
from hr_digital_employee.intake_extraction.extraction import ExtractionService


def test_t3_4_overlapping_dates_are_flagged_as_an_inconsistency() -> None:
    resume_text = (
        "Working Experience:\n"
        "2015-2018 Engineer at Alpha Corp\n"
        "2017-2020 Engineer at Beta Corp\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    inconsistency = next(f for f in flags if f.kind is RedFlagKind.INCONSISTENCY)
    assert inconsistency.neutral_framing is False


def test_t3_6_an_employment_gap_is_framed_as_a_neutral_clarification_item() -> None:
    resume_text = (
        "Working Experience:\n2010-2012 Engineer at Alpha Corp\n2015-2018 Engineer at Beta Corp\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    gap_flag = next(f for f in flags if f.kind is RedFlagKind.EMPLOYMENT_GAP)
    assert gap_flag.neutral_framing is True
    assert "penalty" not in gap_flag.description.lower()
    assert "consider asking" in gap_flag.description.lower()


def test_frequent_short_tenures_are_flagged_neutrally() -> None:
    resume_text = (
        "Working Experience:\n"
        "2018-2019 Engineer at A\n2019-2020 Engineer at B\n2020-2021 Engineer at C\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    frequent_changes = next(f for f in flags if f.kind is RedFlagKind.FREQUENT_JOB_CHANGES)
    assert frequent_changes.neutral_framing is True


def test_repeated_skill_entries_are_flagged_as_keyword_stuffing() -> None:
    resume_text = "Skills:\nPython\nPython\nPython\nPython\n"
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    stuffing = next(f for f in flags if f.kind is RedFlagKind.KEYWORD_STUFFING)
    assert stuffing.neutral_framing is False
    assert "python" in stuffing.description.lower()


def test_no_false_gap_flag_for_a_continuously_employed_candidate_with_overlapping_roles() -> None:
    # Regression: the gap detector compared adjacent *unmerged* ranges after sorting, so a
    # continuous 2015-2020 role containing two shorter overlapping engagements produced a
    # spurious "gap between 2017 and 2018" even though the candidate was employed the whole time.
    resume_text = (
        "Working Experience:\n"
        "2015-2020 Company A\n2016-2017 Company B (concurrent)\n2018-2019 Company C (concurrent)\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    assert not any(f.kind is RedFlagKind.EMPLOYMENT_GAP for f in flags)


def test_no_fabricated_gap_flag_from_a_reversed_typo_date_range() -> None:
    # Regression: an unvalidated reversed range (e.g. a typo'd "2020-2015") was sorted in as-is
    # and combined with a later range into a fabricated, inflated gap claim.
    resume_text = "Working Experience:\n2020-2015 Company X\n2021-2022 Company Y\n"
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    assert not any(f.kind is RedFlagKind.EMPLOYMENT_GAP for f in flags)


def test_two_separate_employment_gaps_are_both_flagged_not_just_the_first() -> None:
    # Regression: `_detect_employment_gap` returned on the first gap found in the loop, so a
    # candidate with two genuinely separate unexplained gaps only ever had the earlier one
    # surfaced -- the second was silently dropped, not merged, just gone.
    resume_text = (
        "Working Experience:\n"
        "2010-2012 Engineer at Alpha Corp\n"
        "2014-2015 Engineer at Beta Corp\n"
        "2018-2020 Engineer at Gamma Corp\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    gap_flags = [f for f in flags if f.kind is RedFlagKind.EMPLOYMENT_GAP]
    assert len(gap_flags) == 2
    assert any("2012" in f.description and "2014" in f.description for f in gap_flags)
    assert any("2015" in f.description and "2018" in f.description for f in gap_flags)


def test_two_separate_overlapping_date_pairs_are_both_flagged_not_just_the_first() -> None:
    # Regression: `_detect_inconsistency` returned on the first overlapping pair found, silently
    # dropping any additional, independent overlap elsewhere in the same resume.
    resume_text = (
        "Working Experience:\n"
        "2010-2012 Engineer at A\n"
        "2011-2013 Engineer at B\n"
        "2015-2017 Engineer at C\n"
        "2016-2018 Engineer at D\n"
    )
    extracted = ExtractionService().extract(resume_text)

    flags = detect_red_flags(extracted)

    inconsistency_flags = [f for f in flags if f.kind is RedFlagKind.INCONSISTENCY]
    assert len(inconsistency_flags) == 2


def test_a_clean_consistent_resume_produces_no_flags() -> None:
    resume_text = (
        "Skills:\nPython\nSQL\n\nWorking Experience:\n2018-2023 Engineer at TechCorp\n"
        "Education:\nBachelor of Computer Science\n"
    )
    extracted = ExtractionService().extract(resume_text)

    assert detect_red_flags(extracted) == ()
