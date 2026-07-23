"""Candidate identity matching and deduplication across channels (SOP 2.1.3)."""

from __future__ import annotations

import unicodedata
import uuid

from hr_digital_employee.intake_extraction.models import (
    Candidate,
    IdentityMatchResult,
    MatchOutcome,
    RawSubmission,
)

_AMBIGUOUS_NAME_SIMILARITY_THRESHOLD = 0.4
"""At/above this: ambiguous, needs a human (SOP 2.1.3 -- never auto-merge on an uncertain match).
Below: treated as a different person (new profile). A name -- even an *exact* full-name match --
is never enough on its own to auto-merge (see MERGED_INTO_EXISTING's `matched_on` handling below):
a name isn't a unique identifier, and two different real candidates sharing one common name would
otherwise be silently merged with no human ever seeing it (ASSUMPTIONS.md)."""


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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_phone(phone: str) -> str:
    """Digits only -- drops spaces/dashes/parens/dots and a leading `+`, so "+1 (555) 123-4567"
    and "15551234567" compare equal instead of being treated as different people's numbers. NFKC
    normalization folds full-width Unicode digits ("１２３...", a realistic artifact of CJK-locale
    input or OCR) to their ASCII equivalents first -- otherwise the same real phone number typed in
    full-width form silently failed to match its ASCII counterpart, duplicating the candidate with
    no human ever flagged (see ASSUMPTIONS.md)."""
    return "".join(char for char in unicodedata.normalize("NFKC", phone) if char.isdigit())


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
        # Compared on the *normalized* value's truthiness, not the raw one -- otherwise two
        # different people whose raw email/phone are non-empty but normalize to the same empty
        # string (e.g. phone "--" and "()", or email "   " and "\t") would collide and auto-merge.
        matched_on: list[str] = []
        if submission.candidate_email and existing.email:
            submission_email = _normalize_email(submission.candidate_email)
            existing_email = _normalize_email(existing.email)
            if submission_email and submission_email == existing_email:
                matched_on.append("email")
        if submission.candidate_phone and existing.phone:
            submission_phone = _normalize_phone(submission.candidate_phone)
            existing_phone = _normalize_phone(existing.phone)
            if submission_phone and submission_phone == existing_phone:
                matched_on.append("phone")

        if matched_on:
            return IdentityMatchResult(
                outcome=MatchOutcome.MERGED_INTO_EXISTING,
                candidate=existing,
                matched_on=matched_on,
            )

        if submission.candidate_name and existing.name:
            similarity = _name_similarity(submission.candidate_name, existing.name)
            if similarity >= _AMBIGUOUS_NAME_SIMILARITY_THRESHOLD:
                return IdentityMatchResult(
                    outcome=MatchOutcome.AMBIGUOUS,
                    candidate=existing,
                    matched_on=["name (uncertain)"],
                )

        return None
