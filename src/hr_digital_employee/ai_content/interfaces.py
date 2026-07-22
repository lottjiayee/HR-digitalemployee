"""Public interface Module 3 exposes downstream (consumed by Module 5)."""

from __future__ import annotations

from hr_digital_employee.ai_content.content_service import (
    ContentGenerationService,
    GeneratedContent,
)
from hr_digital_employee.ai_content.models import (
    AnchoredSentence,
    CandidateSummary,
    InterviewQuestion,
    QuestionAngle,
    RedFlag,
    RedFlagKind,
)

__all__ = [
    "AnchoredSentence",
    "CandidateSummary",
    "ContentGenerationService",
    "GeneratedContent",
    "InterviewQuestion",
    "QuestionAngle",
    "RedFlag",
    "RedFlagKind",
]
