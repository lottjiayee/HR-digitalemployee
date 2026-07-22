"""Candidate identity matching and deduplication across channels (SOP 2.1.3)."""

from __future__ import annotations

import uuid

from hr_digital_employee.intake_extraction.models import (
    Candidate,
    IdentityMatchResult,
    MatchOutcome,
    RawSubmission,
)

_AMBIGUOUS_NAME_SIMILARITY_BAND = (0.4, 0.99)
"""Below this band: treated as a different person (new profile). Within: ambiguous, needs a
human (SOP 2.1.3 -- never auto-merge on an uncertain match). At/above the top: confident match."""


def _name_similarity(a: str, b: str) -> float:
    """Small heuristic name-similarity score in [0, 1] -- not a real fuzzy-match algorithm."""
    a_norm, b_norm = a.strip().lower(), b.strip().lower()
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    a_tokens, b_tokens = set(a_norm.split()), set(b_norm.split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), len(b_tokens))


class IdentityDedupService:
    """Matches incoming submissions against known candidates by email, phone, and name
    similarity -- confident matches merge, ambiguous matches are flagged to a human, never
    auto-merged (SOP 2.1.3)."""

    def __init__(self) -> None:
        self._candidates: list[Candidate] = []

    def known_candidates(self) -> list[Candidate]:
        return list(self._candidates)

    def match(self, submission: RawSubmission) -> IdentityMatchResult:
        # Scan every existing candidate rather than stopping at the first signal found -- a
        # confident match against candidate #2 must win even if candidate #1 only produced a weak,
        # ambiguous signal (SOP 2.1.3: never let a coincidental near-miss block a real match).
        ambiguous_result: IdentityMatchResult | None = None
        for existing in self._candidates:
            result = self._compare(submission, existing)
            if result is None:
                continue
            if result.outcome is MatchOutcome.MERGED_INTO_EXISTING:
                return result
            if ambiguous_result is None:
                ambiguous_result = result
        if ambiguous_result is not None:
            return ambiguous_result

        new_candidate = Candidate(
            candidate_id=str(uuid.uuid4()),
            email=submission.candidate_email,
            phone=submission.candidate_phone,
            name=submission.candidate_name,
        )
        self._candidates.append(new_candidate)
        return IdentityMatchResult(outcome=MatchOutcome.NEW_PROFILE, candidate=new_candidate)

    def _compare(
        self, submission: RawSubmission, existing: Candidate
    ) -> IdentityMatchResult | None:
        matched_on: list[str] = []
        if submission.candidate_email and submission.candidate_email == existing.email:
            matched_on.append("email")
        if submission.candidate_phone and submission.candidate_phone == existing.phone:
            matched_on.append("phone")

        if matched_on:
            return IdentityMatchResult(
                outcome=MatchOutcome.MERGED_INTO_EXISTING,
                candidate=existing,
                matched_on=matched_on,
            )

        if submission.candidate_name and existing.name:
            similarity = _name_similarity(submission.candidate_name, existing.name)
            low, high = _AMBIGUOUS_NAME_SIMILARITY_BAND
            if similarity >= high:
                return IdentityMatchResult(
                    outcome=MatchOutcome.MERGED_INTO_EXISTING,
                    candidate=existing,
                    matched_on=["name"],
                )
            if similarity >= low:
                return IdentityMatchResult(
                    outcome=MatchOutcome.AMBIGUOUS,
                    candidate=existing,
                    matched_on=["name (uncertain)"],
                )

        return None
