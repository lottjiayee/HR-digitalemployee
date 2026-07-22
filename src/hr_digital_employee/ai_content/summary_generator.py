"""Candidate summary generation (design.md §3.5, FR-10).

Consumes Module 1's structured extraction output only -- never raw resume text -- so there is no
code path for a resume to supply "instructions" to the LLM call (module-3 doc §4, test.md T3.5).
"""

from __future__ import annotations

from hr_digital_employee.ai_content.anchoring import anchor_sentences
from hr_digital_employee.ai_content.llm_provider import LLMProvider, TemplateLLMProvider
from hr_digital_employee.ai_content.models import (
    MODEL_VERSION,
    PROMPT_VERSION,
    CandidateSummary,
    SourcePassage,
)
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume, FieldStatus


def build_source_passages(extracted: ExtractedResume) -> tuple[SourcePassage, ...]:
    """The structured fields available to anchor a summary sentence against -- skips any field
    that's `UNVERIFIED`/empty, so no sentence can ever be generated "about" a section the resume
    didn't actually have."""
    passages: list[SourcePassage] = []
    if extracted.skills.status is FieldStatus.VERIFIED and extracted.skills.value:
        passages.append(SourcePassage(field_name="skills", text=", ".join(extracted.skills.value)))
    if extracted.projects.status is FieldStatus.VERIFIED and extracted.projects.value:
        passages.append(
            SourcePassage(field_name="projects", text=", ".join(extracted.projects.value))
        )
    if extracted.experience.status is FieldStatus.VERIFIED and extracted.experience.value:
        passages.append(SourcePassage(field_name="experience", text=extracted.experience.value))
    if extracted.education.status is FieldStatus.VERIFIED and extracted.education.value:
        passages.append(SourcePassage(field_name="education", text=extracted.education.value))
    return tuple(passages)


class SummaryGenerationService:
    """Generates a factual candidate summary with every sentence verified against a source
    passage (FR-10)."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider or TemplateLLMProvider()

    def generate_summary(self, extracted: ExtractedResume) -> CandidateSummary:
        passages = build_source_passages(extracted)
        raw_sentences = self._llm_provider.generate_summary_sentences(passages)
        anchored = anchor_sentences(raw_sentences, passages)
        return CandidateSummary(
            sentences=anchored, model_version=MODEL_VERSION, prompt_version=PROMPT_VERSION
        )
