"""Tests for candidate identity matching and deduplication (SOP 2.1.3, test.md T1.8-T1.9)."""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.models import (
    MatchOutcome,
    RawSubmission,
    SubmissionChannel,
)


def _submission(
    *, email: str | None = None, phone: str | None = None, name: str | None = None
) -> RawSubmission:
    return RawSubmission(
        channel=SubmissionChannel.EMAIL,
        candidate_email=email,
        candidate_phone=phone,
        candidate_name=name,
        file_bytes=b"Skills:\nPython\n",
        received_at=datetime.now(UTC),
    )


def test_first_submission_creates_new_profile() -> None:
    service = IdentityDedupService()
    result = service.match(_submission(email="a@example.com", name="Jane Doe"))

    assert result.outcome is MatchOutcome.NEW_PROFILE
    assert result.candidate is not None
    assert len(service.known_candidates()) == 1


def test_t1_8_matching_email_across_channels_merges_into_existing_profile() -> None:
    service = IdentityDedupService()
    first = service.match(_submission(email="a@example.com", name="Jane Doe"))
    second = service.match(_submission(email="a@example.com", name="Jane Doe"))

    assert first.candidate is not None
    assert second.candidate is not None
    assert second.outcome is MatchOutcome.MERGED_INTO_EXISTING
    assert second.candidate.candidate_id == first.candidate.candidate_id
    assert len(service.known_candidates()) == 1


def test_t1_9_ambiguous_name_similarity_is_flagged_not_auto_merged() -> None:
    service = IdentityDedupService()
    service.match(_submission(name="Jane Doe"))
    result = service.match(_submission(name="Jane D"))

    assert result.outcome is MatchOutcome.AMBIGUOUS
    assert len(service.known_candidates()) == 1  # not merged, not created as new either


def test_clearly_different_name_creates_new_profile() -> None:
    service = IdentityDedupService()
    service.match(_submission(name="Jane Doe"))
    result = service.match(_submission(name="John Smith"))

    assert result.outcome is MatchOutcome.NEW_PROFILE
    assert len(service.known_candidates()) == 2
