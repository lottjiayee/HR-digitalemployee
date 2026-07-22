"""Tests for the offline TemplateLLMProvider stub (design.md §10.2, ASSUMPTIONS.md).

Previously exercised only indirectly through SummaryGenerationService -- these test the provider's
own sentence-construction rules in isolation, including its generic-field fallback branch, which no
existing pipeline test could reach (build_source_passages never emits a field_name outside the four
known ones).
"""

from __future__ import annotations

from hr_digital_employee.ai_content.llm_provider import TemplateLLMProvider
from hr_digital_employee.ai_content.models import SourcePassage


def test_produces_one_sentence_per_non_empty_passage() -> None:
    passages = (
        SourcePassage(field_name="skills", text="Python, SQL"),
        SourcePassage(field_name="education", text="Bachelor of Computer Science"),
    )

    sentences = TemplateLLMProvider().generate_summary_sentences(passages)

    assert len(sentences) == 2


def test_skips_passages_with_blank_or_whitespace_only_text() -> None:
    passages = (
        SourcePassage(field_name="skills", text="Python"),
        SourcePassage(field_name="projects", text="   "),
    )

    sentences = TemplateLLMProvider().generate_summary_sentences(passages)

    assert len(sentences) == 1
    assert "Python" in sentences[0]


def test_falls_back_to_a_generic_sentence_for_an_unrecognized_field_name() -> None:
    passages = (SourcePassage(field_name="certifications", text="AWS Certified"),)

    sentences = TemplateLLMProvider().generate_summary_sentences(passages)

    assert sentences == ("Certifications: AWS Certified.",)
