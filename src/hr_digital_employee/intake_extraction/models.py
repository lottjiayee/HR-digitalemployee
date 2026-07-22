"""Domain models for resume intake and structured extraction (SOP 2.1)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")

MUST_HAVE_CONFIDENCE_THRESHOLD = 0.85
"""SOP 2.1.1: a field backing a must-have criterion below this confidence never enters gating."""


class FieldStatus(enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"  # SOP 2.1.1: never "not met" -- absence is not failure


@dataclass(frozen=True)
class ExtractedField(Generic[T]):
    """A single structured field extracted from a resume, with its confidence."""

    value: T | None
    confidence: float
    status: FieldStatus

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

    @property
    def meets_must_have_confidence(self) -> bool:
        return (
            self.status is FieldStatus.VERIFIED
            and self.confidence >= MUST_HAVE_CONFIDENCE_THRESHOLD
        )


@dataclass(frozen=True)
class ExtractedResume:
    """The four structured pillars extracted from a resume (SOP 2.1)."""

    skills: ExtractedField[list[str]]
    projects: ExtractedField[list[str]]
    experience: ExtractedField[str]
    education: ExtractedField[str]
    parser_version: str


class SubmissionChannel(enum.Enum):
    EMAIL = "email"
    TEAMS = "teams"
    WHATSAPP = "whatsapp"  # gated -- see requirement.md §7 open questions


@dataclass(frozen=True)
class RawSubmission:
    """A resume as received from an intake channel, before any processing."""

    channel: SubmissionChannel
    candidate_email: str | None
    candidate_phone: str | None
    candidate_name: str | None
    file_bytes: bytes
    received_at: datetime

    @property
    def display_identifier(self) -> str:
        """Best available identifier for logging/audit -- never blank, never raises."""
        return self.candidate_email or self.candidate_phone or "unknown"


class QueueReason(enum.Enum):
    LOW_CONFIDENCE_MUST_HAVE = "low_confidence_must_have"
    UNPARSEABLE_FILE = "unparseable_file"
    SUSPECTED_INJECTION = "suspected_injection"
    AMBIGUOUS_IDENTITY_MATCH = "ambiguous_identity_match"
    PROCESSING_ERROR = "processing_error"
    """An exception escaped every known-shape check above (e.g. a corrupted PDF pypdf can't even
    partially parse) -- routed to manual review rather than left to crash the whole intake batch."""


@dataclass(frozen=True)
class ManualReviewItem:
    submission: RawSubmission
    reason: QueueReason
    detail: str
    queued_at: datetime


class MatchOutcome(enum.Enum):
    MERGED_INTO_EXISTING = "merged_into_existing"
    NEW_PROFILE = "new_profile"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    email: str | None
    phone: str | None
    name: str | None


@dataclass(frozen=True)
class IdentityMatchResult:
    outcome: MatchOutcome
    candidate: Candidate | None
    matched_on: list[str] = field(default_factory=list)
