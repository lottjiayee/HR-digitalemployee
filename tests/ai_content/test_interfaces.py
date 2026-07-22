"""Confirms Module 3's downstream-facing interface surface is importable and populated."""

from __future__ import annotations

from hr_digital_employee.ai_content.interfaces import (
    CandidateSummary,
    ContentGenerationService,
    GeneratedContent,
    InterviewQuestion,
    QuestionAngle,
    RedFlag,
    RedFlagKind,
)


def test_downstream_interface_exports_are_the_real_types() -> None:
    assert CandidateSummary.__name__ == "CandidateSummary"
    assert ContentGenerationService.__name__ == "ContentGenerationService"
    assert GeneratedContent.__name__ == "GeneratedContent"
    assert InterviewQuestion.__name__ == "InterviewQuestion"
    assert QuestionAngle.VERIFICATION.value == "verification"
    assert RedFlag.__name__ == "RedFlag"
    assert RedFlagKind.INCONSISTENCY.value == "inconsistency"
