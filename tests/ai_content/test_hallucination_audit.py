"""Tests for the monthly hallucination-audit hook (test.md T3.8)."""

from __future__ import annotations

from hr_digital_employee.ai_content.hallucination_audit import (
    HallucinationAuditLog,
    is_suspension_triggered,
)
from hr_digital_employee.ai_content.models import CandidateSummary, SourcePassage


def _summary() -> CandidateSummary:
    return CandidateSummary(sentences=(), model_version="stub-0.1.0", prompt_version="stub-0.1.0")


def test_t3_8_sample_returns_summaries_alongside_their_source_passages() -> None:
    log = HallucinationAuditLog()
    log.record("cand-1", _summary(), (SourcePassage(field_name="skills", text="Python"),))

    sample = log.sample(10)

    assert len(sample) == 1
    assert sample[0].candidate_id == "cand-1"
    assert sample[0].source_passages[0].text == "Python"


def test_sample_never_returns_more_than_requested() -> None:
    log = HallucinationAuditLog()
    for i in range(5):
        log.record(f"cand-{i}", _summary(), ())

    assert len(log.sample(2)) == 2
    assert len(log.sample(100)) == 5


def test_len_reflects_the_number_of_recorded_summaries() -> None:
    log = HallucinationAuditLog()
    assert len(log) == 0

    log.record("cand-1", _summary(), ())

    assert len(log) == 1


def test_suspension_triggers_when_rate_exceeds_threshold() -> None:
    assert is_suspension_triggered(hallucination_rate=0.1, threshold=0.05) is True
    assert is_suspension_triggered(hallucination_rate=0.02, threshold=0.05) is False
    assert is_suspension_triggered(hallucination_rate=0.05, threshold=0.05) is False
