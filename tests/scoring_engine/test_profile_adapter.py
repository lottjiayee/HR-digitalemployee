"""Tests for the Module 1 -> Module 2 profile adapter (ASSUMPTIONS.md)."""

from __future__ import annotations

from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.models import (
    ExtractedField,
    ExtractedResume,
    FieldStatus,
)
from hr_digital_employee.scoring_engine.models import EducationLevel
from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile


def _resume(
    skills: ExtractedField[list[str]] | None = None,
    projects: ExtractedField[list[str]] | None = None,
    experience: ExtractedField[str] | None = None,
    education: ExtractedField[str] | None = None,
) -> ExtractedResume:
    unverified_list: ExtractedField[list[str]] = ExtractedField(
        value=None, confidence=0.0, status=FieldStatus.UNVERIFIED
    )
    unverified_text: ExtractedField[str] = ExtractedField(
        value=None, confidence=0.0, status=FieldStatus.UNVERIFIED
    )
    return ExtractedResume(
        skills=skills if skills is not None else unverified_list,
        projects=projects if projects is not None else unverified_list,
        experience=experience if experience is not None else unverified_text,
        education=education if education is not None else unverified_text,
        parser_version="stub-0.1.0",
    )


def _verified(value: str) -> ExtractedField[str]:
    return ExtractedField(value=value, confidence=0.95, status=FieldStatus.VERIFIED)


def test_skills_pass_through_when_verified() -> None:
    resume = _resume(
        skills=ExtractedField(value=["Python", "SQL"], confidence=0.95, status=FieldStatus.VERIFIED)
    )

    profile = build_candidate_profile(resume)

    assert profile.skills == ("Python", "SQL")


def test_skills_are_empty_when_unverified() -> None:
    profile = build_candidate_profile(_resume())

    assert profile.skills == ()


def test_years_of_experience_from_an_explicit_years_phrase() -> None:
    resume = _resume(experience=_verified("5 years at TechCorp as a backend engineer"))

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 5.0


def test_years_of_experience_prefers_the_largest_explicit_mention() -> None:
    resume = _resume(
        experience=_verified("8 years total experience, including 3 years as a team lead")
    )

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 8.0


def test_years_of_experience_falls_back_to_summed_year_ranges() -> None:
    resume = _resume(
        experience=_verified(
            "1999-2002 Counseling Supervisor, The Wesley Center\n"
            "1997-1999 Client Specialist, Rainbow Special Care Center"
        )
    )

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 5.0  # (2002-1999) + (1999-1997) = 3 + 2


def test_years_of_experience_range_fallback_does_not_overcount_a_career_break() -> None:
    # A max-min "span" would wrongly count 2008-2013 (the gap) as experience too (2020-2005=15).
    # Summing each range's own length gives the correct total: (2007-2005) + (2020-2013) = 9.
    resume = _resume(
        experience=_verified(
            "2013-2020 Senior Engineer, Example Corp\n2005-2007 Junior Engineer, Other Corp"
        )
    )

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 9.0


def test_years_of_experience_range_fallback_merges_overlapping_concurrent_roles() -> None:
    # Regression: summing each range's own length without merging overlaps double-counted a
    # concurrent side engagement -- (2015-2020) + (2016-2019) used to give 5 + 3 = 8 instead of
    # the correct 5-year calendar span the two overlapping roles actually cover.
    resume = _resume(
        experience=_verified(
            "2015-2020 Senior Engineer, Example Corp\n2016-2019 Side Contractor, Other Corp"
        )
    )

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 5.0


def test_years_of_experience_ignores_a_reversed_date_range() -> None:
    resume = _resume(experience=_verified("2020-2015 Typo'd Range, Some Corp"))

    profile = build_candidate_profile(resume)

    assert profile.years_of_experience == 0.0


def test_years_of_experience_is_zero_when_experience_is_unverified() -> None:
    profile = build_candidate_profile(_resume())

    assert profile.years_of_experience == 0.0


def test_education_level_recognizes_bachelor() -> None:
    resume = _resume(education=_verified("Bachelor of Computer Science"))
    assert build_candidate_profile(resume).education_level is EducationLevel.BACHELOR


def test_education_level_recognizes_bs_abbreviation() -> None:
    resume = _resume(education=_verified("- BS in Early Childhood Development (1999)"))
    assert build_candidate_profile(resume).education_level is EducationLevel.BACHELOR


def test_education_level_recognizes_bba_abbreviation() -> None:
    resume = _resume(education=_verified("BBA, Example Business School"))
    assert build_candidate_profile(resume).education_level is EducationLevel.BACHELOR


def test_education_level_recognizes_master() -> None:
    resume = _resume(education=_verified("MBA, Example Business School"))
    assert build_candidate_profile(resume).education_level is EducationLevel.MASTER


def test_education_level_recognizes_doctorate() -> None:
    resume = _resume(education=_verified("PhD in Computer Science"))
    assert build_candidate_profile(resume).education_level is EducationLevel.DOCTORATE


def test_education_level_recognizes_high_school() -> None:
    resume = _resume(education=_verified("High School Diploma"))
    assert build_candidate_profile(resume).education_level is EducationLevel.HIGH_SCHOOL


def test_education_level_is_none_when_unverified() -> None:
    profile = build_candidate_profile(_resume())
    assert profile.education_level is EducationLevel.NONE


def test_education_level_is_none_when_no_keyword_is_recognized() -> None:
    resume = _resume(education=_verified("Example University, Little Rock, AR"))
    assert build_candidate_profile(resume).education_level is EducationLevel.NONE


def test_project_count_from_verified_projects() -> None:
    resume = _resume(
        projects=ExtractedField(
            value=["Built a pipeline", "Led a small team"],
            confidence=0.95,
            status=FieldStatus.VERIFIED,
        )
    )
    assert build_candidate_profile(resume).project_count == 2


def test_project_count_is_zero_when_unverified() -> None:
    assert build_candidate_profile(_resume()).project_count == 0


def test_full_pipeline_from_a_real_extraction_service_run() -> None:
    resume_text = (
        "Skills:\nPython\nSQL\n\n"
        "Projects:\nBuilt a data pipeline\nLed a small team\n\n"
        "Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
        "Education:\nBachelor of Computer Science\n"
    )
    extracted = ExtractionService().extract(resume_text)

    profile = build_candidate_profile(extracted)

    assert profile.skills == ("Python", "SQL")
    assert profile.years_of_experience == 5.0
    assert profile.education_level is EducationLevel.BACHELOR
    assert profile.project_count == 2
