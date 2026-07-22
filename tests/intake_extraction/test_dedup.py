"""Tests for candidate identity matching and deduplication (SOP 2.1.3, test.md T1.8-T1.9)."""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.models import (
    Candidate,
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


def test_a_confident_match_wins_even_when_a_weaker_ambiguous_candidate_comes_first() -> None:
    # Regression test: matching used to stop at the first candidate with *any* signal, so an
    # unrelated candidate's weak name overlap could block a later, confident match from being
    # found. Uses email (a hard identifier) for "confident" -- name alone is never confident
    # enough to auto-merge, see the test below.
    service = IdentityDedupService()
    service._candidates.append(
        Candidate(candidate_id="c1", email=None, phone=None, name="John Smyth")
    )
    service._candidates.append(
        Candidate(candidate_id="c2", email="john@example.com", phone=None, name="Someone Else")
    )

    result = service.match(_submission(email="john@example.com", name="John Smith"))

    assert result.outcome is MatchOutcome.MERGED_INTO_EXISTING
    assert result.candidate is not None
    assert result.candidate.candidate_id == "c2"


def test_an_exact_name_match_with_no_corroborating_email_or_phone_is_ambiguous_not_merged() -> (
    None
):
    # Regression: an *exact* full-name match with no other signal used to auto-merge outright --
    # a name isn't a unique identifier, and two different real people can share one common name
    # with no way to tell them apart from name alone. Must go to a human, never auto-merge.
    service = IdentityDedupService()
    service.match(_submission(name="John Smith"))  # no email/phone, e.g. a WhatsApp submission

    result = service.match(_submission(name="John Smith"))  # a *different* real person

    assert result.outcome is MatchOutcome.AMBIGUOUS
    assert len(service.known_candidates()) == 1


def test_email_matching_is_case_insensitive() -> None:
    # Regression: a case-only difference (e.g. resubmitting via a channel that capitalizes
    # differently) used to be treated as a different email entirely, silently splitting one real
    # person into two separate candidate profiles.
    service = IdentityDedupService()
    first = service.match(_submission(email="Elizabeth.Windsor@Example.com", name="Liz W"))
    second = service.match(_submission(email="elizabeth.windsor@example.com", name="Elizabeth W"))

    assert second.outcome is MatchOutcome.MERGED_INTO_EXISTING
    assert second.candidate is not None
    assert first.candidate is not None
    assert second.candidate.candidate_id == first.candidate.candidate_id


def test_phone_matching_ignores_common_formatting_differences() -> None:
    service = IdentityDedupService()
    first = service.match(_submission(phone="+1 (555) 123-4567", name="Jane Doe"))
    second = service.match(_submission(phone="15551234567", name="Jane Doe"))

    assert second.outcome is MatchOutcome.MERGED_INTO_EXISTING
    assert second.candidate is not None
    assert first.candidate is not None
    assert second.candidate.candidate_id == first.candidate.candidate_id


def test_two_different_people_with_punctuation_only_phones_are_not_merged() -> None:
    # Regression: the truthiness guard checked the RAW phone/email string was non-empty, then
    # compared NORMALIZED values -- so two different non-empty raw values that both normalize to
    # "" (e.g. placeholder punctuation with no digits) compared equal and silently auto-merged two
    # unrelated people.
    service = IdentityDedupService()
    service.match(_submission(phone="--", name="Alice Anderson"))
    second = service.match(_submission(phone="()", name="Bob Baker"))

    assert second.outcome is not MatchOutcome.MERGED_INTO_EXISTING


def test_two_different_people_with_whitespace_only_emails_are_not_merged() -> None:
    service = IdentityDedupService()
    service.match(_submission(email="   ", name="Alice Anderson"))
    second = service.match(_submission(email="\t", name="Bob Baker"))

    assert second.outcome is not MatchOutcome.MERGED_INTO_EXISTING
