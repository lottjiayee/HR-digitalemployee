"""Domain models for AI-Assisted Content Generation (design.md §3.5; FR-10, FR-12).

No field here ever carries a score, tier, or gating value -- that separation is what FR-9
("LLM-assisted output never alters score/tier/gating") rests on, enforced by construction: nothing
in this module can write to `scoring_engine.models.Score`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

MODEL_VERSION = "stub-0.1.0"
"""Stamped on every generated summary/questions/flags collection, alongside PROMPT_VERSION."""

PROMPT_VERSION = "stub-0.1.0"


@dataclass(frozen=True)
class SourcePassage:
    """One piece of Module 1's structured extraction output a sentence can be anchored to."""

    field_name: str
    text: str


@dataclass(frozen=True)
class AnchoredSentence:
    """A summary sentence together with the source passage it was verified against (FR-10)."""

    text: str
    source_field: str


@dataclass(frozen=True)
class CandidateSummary:
    """The factual candidate summary. Only sentences that survived anchor verification are
    present -- an unanchored sentence is dropped before this object is ever constructed."""

    sentences: tuple[AnchoredSentence, ...]
    model_version: str
    prompt_version: str


class QuestionAngle(enum.Enum):
    VERIFICATION = "verification"
    GAP = "gap"
    BEHAVIORAL = "behavioral"


@dataclass(frozen=True)
class InterviewQuestion:
    angle: QuestionAngle
    text: str


class RedFlagKind(enum.Enum):
    INCONSISTENCY = "inconsistency"
    KEYWORD_STUFFING = "keyword_stuffing"
    FREQUENT_JOB_CHANGES = "frequent_job_changes"
    EMPLOYMENT_GAP = "employment_gap"


@dataclass(frozen=True)
class RedFlag:
    """A red-flag hint surfaced to HR. `neutral_framing` is True for kinds module-3 doc §4 calls
    out as fairness-sensitive (employment gaps, job-change frequency) -- their `description` reads
    as a neutral interview-clarification prompt, never an accusation or automatic penalty."""

    kind: RedFlagKind
    description: str
    neutral_framing: bool
