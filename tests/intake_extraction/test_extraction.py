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


def test_t1_12_chinese_section_headers_are_recognized_same_as_english() -> None:
    # Regression: the header regex was English-keyword-only, so a resume using Chinese section
    # headers (a real scenario per SOP 2.1.1's "mixed Chinese-English text" validation
    # requirement) had every field UNVERIFIED even with clearly-structured, complete content --
    # violating the SOP's own consistency guarantee that identical qualifications must produce
    # identical outcomes regardless of language mix.
    resume = """\
技能：
Python
SQL

项目：
Built a data pipeline

工作经验：
5 years at TechCorp as a backend engineer

教育背景：
Bachelor of Computer Science
"""
    extracted = ExtractionService().extract(resume)

    assert extracted.skills.status is FieldStatus.VERIFIED
    assert extracted.skills.value == ["Python", "SQL"]
    assert extracted.projects.status is FieldStatus.VERIFIED
    assert extracted.experience.status is FieldStatus.VERIFIED
    assert extracted.education.status is FieldStatus.VERIFIED


def test_t1_12_bilingual_section_headers_on_one_line_are_recognized() -> None:
    # A header stating both languages together (e.g. "Skills · 技能"), common on Hong Kong
    # bilingual resume templates, must also resolve -- not just headers purely in one language.
    resume = """\
Skills · 技能:
Python

Working Experience · 工作经验:
5 years at TechCorp

Education · 教育背景:
Bachelor of Computer Science
"""
    extracted = ExtractionService().extract(resume)

    assert extracted.skills.status is FieldStatus.VERIFIED
    assert extracted.experience.status is FieldStatus.VERIFIED
    assert extracted.education.status is FieldStatus.VERIFIED


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


def test_a_prose_sentence_ending_in_a_section_word_does_not_steal_the_real_headers_slot() -> None:
    # Regression: the header regex used to require only "keyword + optional colon + newline"
    # anywhere in the text, with no anchor -- an ordinary prose line ending in a bare section
    # word (no trailing punctuation) satisfied that just as well as a real standalone header,
    # consuming that section's one marker slot before the real header was ever reached. Real
    # Education content was silently absorbed into Experience instead of its own field.
    resume_text = (
        "Summary:\nPassionate about continuous learning and education\n\n"
        "Skills:\nPython, SQL\n\n"
        "Working Experience:\n5 years at TechCorp as backend engineer\n\n"
        "Education:\nBachelor of Computer Science, MIT, 2015\n"
    )
    resume = ExtractionService().extract(resume_text)

    assert resume.education.status is FieldStatus.VERIFIED
    assert resume.education.value == "Bachelor of Computer Science, MIT, 2015"
    assert "MIT" not in (resume.experience.value or "")


def test_a_short_subheading_ending_in_a_section_word_is_still_recognized() -> None:
    # Counterpart to the regression above: a short label-like subheading (not a full sentence)
    # must still be recognized, matching the real-world-template behavior this module already
    # relies on elsewhere (e.g. "Adult Care Experience").
    resume_text = "Adult Care Experience\n5 years, Example Center\n\nEducation:\nBSc"
    resume = ExtractionService().extract(resume_text)

    assert resume.experience.status is FieldStatus.VERIFIED
    assert "Example Center" in resume.experience.value


def test_employment_history_header_is_recognized_as_experience() -> None:
    resume_text = "Skills:\nExcel\n\nEmployment History:\n5 years as a server\n\nEducation:\nBSc"
    resume = ExtractionService().extract(resume_text)

    assert resume.experience.status is FieldStatus.VERIFIED
    assert resume.experience.value == "5 years as a server"


# Regression fixture: anonymized structure of a real student resume run through the pipeline
# during manual testing. Headers the extractor doesn't recognize ("SUMMARY", "VOLUNTEER &
# LEADERSHIP") aren't dropped -- they silently become part of whichever recognized section
# precedes them. "SKILLS AND LANGUAGES" only matches at all because "Technical Skills" contains a
# bare, unanchored "Skills\n" substring -- the header regex has no start-of-line anchor. This
# captures today's stub behavior (see ASSUMPTIONS.md), not a spec guarantee; if extraction.py's
# heuristics change, this test should be revisited deliberately rather than just updated to match.
REAL_WORLD_MULTI_SECTION_RESUME = """\
JANE DOE
+1 5551234567 | jane.doe@example.com | Malaysia
SUMMARY
Detail-oriented Computer Science student with hands-on experience.
EDUCATION
Example University Oct 2023 - Present
Bachelor of Computer Science (Hons)
PROJECTS
Sample Project May 2026
Built ETL pipelines and cleaned datasets.
VOLUNTEER & LEADERSHIP
Vice Secretary, Sample Club Jan 2025 - Jan 2026
Coordinated administrative operations.
SKILLS AND LANGUAGES
Technical Skills
Programming Languages: C++, Python, JavaScript
Languages
Chinese (Fluent), English (Intermediate)
"""


def test_real_world_resume_unrecognized_headers_are_absorbed_by_previous_section() -> None:
    resume = ExtractionService().extract(REAL_WORLD_MULTI_SECTION_RESUME)

    assert resume.education.value == (
        "Example University Oct 2023 - Present\nBachelor of Computer Science (Hons)"
    )
    assert resume.experience.status is FieldStatus.UNVERIFIED
    # "VOLUNTEER & LEADERSHIP" has no recognized header of its own -- it's absorbed into Projects.
    assert resume.projects.value is not None
    assert "VOLUNTEER & LEADERSHIP" in resume.projects.value
    # "SKILLS AND LANGUAGES" itself isn't the match point -- "Technical Skills" is, so the
    # captured section starts one line later than a human would expect.
    assert resume.skills.status is FieldStatus.VERIFIED
    assert resume.skills.value == [
        "Programming Languages: C++, Python, JavaScript",
        "Languages",
        "Chinese (Fluent), English (Intermediate)",
    ]


# Regression fixture: anonymized structure of a real "functional resume" template run through the
# pipeline during manual testing. Multiple experience-like subheadings ("Adult Care Experience",
# "Childcare Experience", "Employment History") with no single literal "Skills"/"Projects"
# heading anywhere in the document.
REAL_WORLD_FUNCTIONAL_RESUME = """\
Career Summary
Four years experience in early childhood development with a diverse background.
Adult Care Experience
- Determined work placement for 150 special needs adult clients.
- Maintained client databases and records.
Childcare Experience
- Coordinated service assignments for 20 part-time counselors.
- Oversaw daily activity and outing planning for 100 clients.
Employment History
1999-2002 Counseling Supervisor, The Wesley Center, Little Rock, Arkansas.
1997-1999 Client Specialist, Rainbow Special Care Center, Little Rock, Arkansas
Education
Example University, Little Rock, AR
- BS in Early Childhood Development (1999)
"""


def test_real_world_resume_with_multiple_experience_subheadings_consolidates_into_one_field() -> (
    None
):
    resume = ExtractionService().extract(REAL_WORLD_FUNCTIONAL_RESUME)

    assert resume.education.value == (
        "Example University, Little Rock, AR\n- BS in Early Childhood Development (1999)"
    )
    assert resume.experience.status is FieldStatus.VERIFIED
    assert "Counseling Supervisor" in resume.experience.value
    # Absorbed, not split into separate fields -- there's only one "experience" pillar.
    assert "Childcare Experience" in resume.experience.value
    assert "Employment History" in resume.experience.value
    # No literal "Skills" or "Projects" heading anywhere in this template.
    assert resume.skills.status is FieldStatus.UNVERIFIED
    assert resume.projects.status is FieldStatus.UNVERIFIED
