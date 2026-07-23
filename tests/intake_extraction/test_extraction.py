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


def test_low_ocr_confidence_caps_field_confidence_even_when_text_is_long_enough() -> None:
    # Regression, found via a real downloaded resume template image: confidence used to be a pure
    # length heuristic (>=10 characters -> 0.95), so a section header Tesseract happened to OCR
    # correctly, followed by unreadable garbled content, still scored VERIFIED/meets-must-have-
    # confidence -- the SOP 2.1.1 confidence gate meant to catch exactly this never fired. A real
    # garbled image scored ~0.41 average OCR confidence vs. ~0.95 for a clean one.
    garbled_but_long_experience = (
        "08 Posmon Tus (c) sh mma ce nang are Lowe um ony yt ps Deseny ry sad omy tay ac nd"
    )
    resume_text = f"Working Experience:\n{garbled_but_long_experience}\n"

    low_confidence_result = ExtractionService().extract(resume_text, ocr_confidence=0.41)
    assert low_confidence_result.experience.status is FieldStatus.VERIFIED
    assert low_confidence_result.experience.confidence == 0.41
    assert low_confidence_result.experience.meets_must_have_confidence is False

    # No OCR confidence signal (e.g. a real PDF text layer, or plain text) -- unaffected, the
    # length heuristic alone still applies, exactly as before this fix.
    no_ocr_result = ExtractionService().extract(resume_text)
    assert no_ocr_result.experience.confidence == 0.95
    assert no_ocr_result.experience.meets_must_have_confidence is True

    # A clean/high-confidence OCR result doesn't get needlessly penalized either.
    high_confidence_result = ExtractionService().extract(resume_text, ocr_confidence=0.97)
    assert high_confidence_result.experience.confidence == 0.95
    assert high_confidence_result.experience.meets_must_have_confidence is True


def test_comma_separated_skills_on_one_line_are_split_into_individual_skills() -> None:
    # Regression, found via a real downloaded resume (not a synthetic fixture): a comma-separated
    # skills line is a very common real-world format, but was previously kept as one single list
    # item (splitlines() only) -- so a candidate clearly listing "Java, C#, Linux" scored 0% on
    # every one of those as a required mandatory skill, since exact skill-name matching can never
    # match a required skill against a whole unsplit line.
    resume = ExtractionService().extract(
        "Skills:\nC, Java, Sdlc, Software Development, Linux, C#, Communication Skills\n\n"
        "Working Experience:\n5 years at TechCorp\n\nEducation:\nBSc\n"
    )

    assert resume.skills.status is FieldStatus.VERIFIED
    assert resume.skills.value == [
        "C",
        "Java",
        "Sdlc",
        "Software Development",
        "Linux",
        "C#",
        "Communication Skills",
    ]


def test_skills_split_on_commas_still_supports_one_skill_per_line() -> None:
    resume = ExtractionService().extract(SAMPLE_RESUME)

    assert resume.skills.value == ["Python", "SQL", "Machine Learning"]


def test_a_category_label_prefix_does_not_stay_glued_to_the_first_split_skill() -> None:
    # Regression: a skills line prefixed with a category label (e.g. "Programming Languages:
    # C++, Python, JavaScript" -- a real, common resume format) used to leave the label glued to
    # the first split skill ("Programming Languages: C++"), an exact-match failure for that one
    # skill even though every other skill on the same line split correctly.
    resume = ExtractionService().extract(
        "Skills:\nProgramming Languages: C++, Python, JavaScript\n\n"
        "Working Experience:\n5 years at TechCorp\n\nEducation:\nBSc\n"
    )

    assert resume.skills.value == ["C++", "Python", "JavaScript"]


def test_a_skills_line_with_no_category_label_is_unaffected() -> None:
    resume = ExtractionService().extract(
        "Skills:\nChinese (Fluent), English (Intermediate)\n\n"
        "Working Experience:\n5 years at TechCorp\n\nEducation:\nBSc\n"
    )

    assert resume.skills.value == ["Chinese (Fluent)", "English (Intermediate)"]


def test_chinese_full_width_comma_separated_skills_are_split() -> None:
    # Regression (round 6): the comma-split only recognized the ASCII "," -- standard Chinese
    # typography uses the full-width "，" instead, so a Chinese comma-separated skills line
    # reproduced the exact "scored 0% despite listing every skill" bug already fixed for English.
    resume = ExtractionService().extract(
        "技能\nC++，Python，Java，Linux\n\n经历\n软件工程师\n"
    )

    assert resume.skills.value == ["C++", "Python", "Java", "Linux"]


def test_chinese_category_label_with_full_width_colon_does_not_stay_glued_to_first_skill() -> None:
    # Regression (round 6): the category-label stripper only recognized the ASCII ":" -- a
    # Chinese label using the full-width "：" (e.g. "编程语言：C++，Python，Java") left the whole
    # line, label included, as one unsplit skill.
    resume = ExtractionService().extract(
        "技能\n编程语言：C++，Python，Java\n\n经历\n软件工程师\n"
    )

    assert resume.skills.value == ["C++", "Python", "Java"]


def test_trailing_contact_info_with_no_closing_header_is_dropped_from_the_section() -> None:
    # Regression, found via a real downloaded resume: its contact block (name/email/phone/city)
    # sits at the very end of the document, after the last recognized header (Education), with no
    # closing header of its own -- the email and phone number were silently absorbed into the
    # "education" field's value. Email/phone are never legitimate section content, so they're
    # filtered out regardless of where they land; a bare name or city isn't reliably
    # distinguishable from real content and is left alone (see ASSUMPTIONS.md).
    resume_text = (
        "Education:\nBachelor's Degree in Computer Science\nZirkel College\n"
        "Jenny Ashcroft\njenny@gmail.com\n+1 213 555-0123.\nLos Angeles, CA\n"
    )
    resume = ExtractionService().extract(resume_text)

    assert resume.education.status is FieldStatus.VERIFIED
    assert "jenny@gmail.com" not in (resume.education.value or "")
    assert "213 555-0123" not in (resume.education.value or "")
    assert "Bachelor's Degree in Computer Science" in (resume.education.value or "")


def test_a_standalone_tenure_date_range_is_not_dropped_as_phone_like() -> None:
    # Regression: a bare "2019 - 2023" line under a job title is a common, legitimate layout, and
    # also happens to satisfy the phone-like digit/separator check (8 digits, only "-"/space
    # characters) -- silently deleting it left profile_adapter.py's year-range fallback with
    # nothing to find, zeroing years_of_experience for an otherwise fully-qualified candidate.
    resume_text = (
        "Working Experience:\nSenior Developer at TechCorp\n2019 - 2023\n"
        "Led backend development for a payments platform.\n\nEducation:\nBSc\n"
    )
    resume = ExtractionService().extract(resume_text)

    assert resume.experience.value == (
        "Senior Developer at TechCorp\n2019 - 2023\n"
        "Led backend development for a payments platform."
    )

    from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile

    assert build_candidate_profile(resume).years_of_experience == 4.0


def test_an_open_ended_tenure_range_is_not_dropped_as_phone_like() -> None:
    resume_text = (
        "Working Experience:\nSenior Developer at TechCorp\n2020 - Present\n"
        "Leading the platform team.\n\nEducation:\nBSc\n"
    )
    resume = ExtractionService().extract(resume_text)

    assert "2020 - Present" in (resume.experience.value or "")


def test_a_bare_iso_date_line_is_not_dropped_as_phone_like() -> None:
    # Regression (round 6): a job's bare ISO-format start date (e.g. "2023-01-15") has >=7 digits
    # and consists only of digits/dashes -- exactly what the phone-like heuristic looks for -- so
    # it was silently deleted, the same consistency-guarantee failure class as the year-range
    # fix above, just not fully closed by it (a single date has no second year to match).
    resume_text = (
        "Working Experience:\nSenior Backend Engineer, Acme Corp\n2023-01-15\n"
        "Led migration of the payments platform to a new architecture.\n\nEducation:\nBSc\n"
    )
    resume = ExtractionService().extract(resume_text)

    assert "2023-01-15" in (resume.experience.value or "")


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
    # captured section starts one line later than a human would expect. Each line is also split
    # on commas, and a leading "Category:" label is dropped so it doesn't stay glued to the first
    # split skill -- "C++", "Python", and "JavaScript" are all individually matchable.
    assert resume.skills.status is FieldStatus.VERIFIED
    assert resume.skills.value == [
        "C++",
        "Python",
        "JavaScript",
        "Languages",
        "Chinese (Fluent)",
        "English (Intermediate)",
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
