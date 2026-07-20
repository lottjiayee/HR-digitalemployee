"""Tests for the (stub) structured extraction service (SOP 2.1, test.md §1)."""

from __future__ import annotations

from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.models import FieldStatus

SAMPLE_RESUME = """\
Skills:
Python
SQL
Machine Learning

Projects:
Built a data pipeline
Led a small team

Working Experience:
5 years at TechCorp as a backend engineer

Education:
Bachelor of Computer Science
"""


def test_t1_3_extracts_all_four_pillars_with_confidence() -> None:
    resume = ExtractionService().extract(SAMPLE_RESUME)

    assert resume.skills.status is FieldStatus.VERIFIED
    assert resume.skills.value == ["Python", "SQL", "Machine Learning"]
    assert resume.skills.meets_must_have_confidence is True

    assert resume.experience.status is FieldStatus.VERIFIED
    assert resume.experience.meets_must_have_confidence is True

    assert resume.education.status is FieldStatus.VERIFIED
    assert resume.projects.status is FieldStatus.VERIFIED


def test_t1_5_missing_section_is_unverified_not_failed() -> None:
    text_without_education = "Skills:\nPython\n\nWorking Experience:\n5 years engineering"
    resume = ExtractionService().extract(text_without_education)

    assert resume.education.status is FieldStatus.UNVERIFIED
    assert resume.education.value is None
    assert resume.education.meets_must_have_confidence is False


def test_thin_section_content_yields_low_confidence_not_disqualification() -> None:
    thin_experience = "Skills:\nPython\n\nWorking Experience:\nN/A\n\nEducation:\nBSc"
    resume = ExtractionService().extract(thin_experience)

    assert resume.experience.status is FieldStatus.VERIFIED  # extracted, just low-confidence
    assert resume.experience.confidence < 0.85
    assert resume.experience.meets_must_have_confidence is False


def test_work_history_header_is_recognized_as_experience() -> None:
    # Real-world resumes commonly say "Work History" rather than the literal word "Experience" --
    # the section-header regex must recognize this common phrasing (see ASSUMPTIONS.md).
    resume_text = "Skills:\nExcel\n\nWork History:\n5 years as a server\n\nEducation:\nBSc"
    resume = ExtractionService().extract(resume_text)

    assert resume.experience.status is FieldStatus.VERIFIED
    assert resume.experience.value == "5 years as a server"
    # The Skills section must stop at "Work History:", not swallow it.
    assert resume.skills.value == ["Excel"]


def test_employment_history_header_is_recognized_as_experience() -> None:
    resume_text = "Skills:\nExcel\n\nEmployment History:\n5 years as a server\n\nEducation:\nBSc"
    resume = ExtractionService().extract(resume_text)

    assert resume.experience.status is FieldStatus.VERIFIED
    assert resume.experience.value == "5 years as a server"
