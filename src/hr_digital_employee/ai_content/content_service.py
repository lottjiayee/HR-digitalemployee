"""Orchestrates the LLM-Assisted Service's three outputs for one candidate (design.md §3.5):
summary, interview questions, red flags. All three read only Module 1's structured extraction
output and Module 2's `Score` -- never raw resume text, never write back to score/tier/gating
(FR-9's isolation is enforced by this module never importing anything that could).
"""

from __future__ import annotations

from dataclasses import dataclass

from hr_digital_employee.ai_content.hallucination_audit import HallucinationAuditLog
from hr_digital_employee.ai_content.interview_questions import generate_interview_questions
from hr_digital_employee.ai_content.llm_provider import LLMProvider
from hr_digital_employee.ai_content.models import CandidateSummary, InterviewQuestion, RedFlag
from hr_digital_employee.ai_content.red_flags import detect_red_flags
from hr_digital_employee.ai_content.summary_generator import (
    SummaryGenerationService,
    build_source_passages,
)
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume
from hr_digital_employee.scoring_engine.interfaces import Score


@dataclass(frozen=True)
class GeneratedContent:
    summary: CandidateSummary
    interview_questions: tuple[InterviewQuestion, ...]
    red_flags: tuple[RedFlag, ...]


class ContentGenerationService:
    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        audit_log: HallucinationAuditLog | None = None,
    ) -> None:
        self._summary_service = SummaryGenerationService(llm_provider)
        self._audit_log = audit_log

    def generate(
        self, candidate_id: str, extracted: ExtractedResume, score: Score
    ) -> GeneratedContent:
        summary = self._summary_service.generate_summary(extracted)
        if self._audit_log is not None:
            self._audit_log.record(candidate_id, summary, build_source_passages(extracted))
        return GeneratedContent(
            summary=summary,
            interview_questions=generate_interview_questions(score, extracted),
            red_flags=detect_red_flags(extracted),
        )
