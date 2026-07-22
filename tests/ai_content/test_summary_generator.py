"""Tests for candidate summary generation (FR-10, test.md T3.1-T3.2, T3.5)."""

from __future__ import annotations

from hr_digital_employee.ai_content.llm_provider import TemplateLLMProvider
from hr_digital_employee.ai_content.models import SourcePassage
from hr_digital_employee.ai_content.summary_generator import (
    SummaryGenerationService,
    build_source_passages,
)
from hr_digital_employee.intake_extraction.extraction import ExtractionService

SAMPLE_RESUME = (
    "Skills:\nPython\nSQL\n\n"
    "Projects:\nBuilt a data pipeline\n\n"
    "Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    "Education:\nBachelor of Computer Science\n"
)


class _HallucinatingProvider:
    """Fake provider standing in for a real LLM that sometimes fabricates a claim -- proves the
    anchoring safety net works regardless of which provider is plugged in (T3.2)."""

    def generate_summary_sentences(self, passages: tuple[SourcePassage, ...]) -> tuple[str, ...]:
        return (
            "The candidate lists the following skills: Python, SQL.",  # grounded
            "The candidate won a national chess championship in 2015.",  # fabricated
        )


def test_build_source_passages_skips_unverified_fields() -> None:
    extracted = ExtractionService().extract("Skills:\nPython\n")

    passages = build_source_passages(extracted)

    assert {p.field_name for p in passages} == {"skills"}


def test_t3_1_every_sentence_in_the_generated_summary_is_anchored() -> None:
    extracted = ExtractionService().extract(SAMPLE_RESUME)

    summary = SummaryGenerationService().generate_summary(extracted)

    assert len(summary.sentences) > 0
    valid_fields = {"skills", "projects", "experience", "education"}
    assert all(s.source_field in valid_fields for s in summary.sentences)


def test_t3_2_an_unanchored_sentence_from_the_llm_provider_is_dropped() -> None:
    extracted = ExtractionService().extract(SAMPLE_RESUME)

    summary = SummaryGenerationService(llm_provider=_HallucinatingProvider()).generate_summary(
        extracted
    )

    texts = [s.text for s in summary.sentences]
    assert "The candidate lists the following skills: Python, SQL." in texts
    assert not any("chess championship" in text for text in texts)


def test_summary_is_stamped_with_model_and_prompt_version() -> None:
    extracted = ExtractionService().extract(SAMPLE_RESUME)

    summary = SummaryGenerationService().generate_summary(extracted)

    assert summary.model_version
    assert summary.prompt_version


def test_template_provider_produces_nothing_for_a_completely_unverified_resume() -> None:
    extracted = ExtractionService().extract("")

    summary = SummaryGenerationService().generate_summary(extracted)

    assert summary.sentences == ()


def test_template_provider_is_the_default_when_none_is_given() -> None:
    assert isinstance(SummaryGenerationService()._llm_provider, TemplateLLMProvider)
