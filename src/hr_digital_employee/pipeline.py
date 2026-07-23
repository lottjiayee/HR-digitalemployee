"""Shared Module 1 -> Module 2 pipeline runner: intake, extraction, dedup, and scoring against a
single JRP. Used by both the CLI report (cli.py) and Module 5's dashboard (presentation/) so this
wiring exists in exactly one place rather than being duplicated across entry points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hr_digital_employee.governance_audit.interfaces import AuditLog
from hr_digital_employee.intake_extraction.channel_adapters import LocalFolderChannelAdapter
from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.gateway import IngestionGateway
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.models import Candidate
from hr_digital_employee.intake_extraction.text_extraction_log import TextExtractionLog
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import JRP, Score
from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile


@dataclass(frozen=True)
class CandidateResult:
    candidate: Candidate
    extracted: ExtractedResume
    score: Score


def run_pipeline(
    resumes_folder: Path,
    jrp: JRP,
    audit_log: AuditLog,
    text_log: TextExtractionLog | None = None,
) -> tuple[list[CandidateResult], ManualReviewQueue]:
    """Run the intake -> extraction -> scoring pipeline once against every file currently in
    `resumes_folder`. Returns per-candidate results sorted by total_score descending, plus the
    manual-review queue for anything that never made it to a Score."""
    manual_review_queue = ManualReviewQueue()
    gateway = IngestionGateway(
        channel_adapters=[LocalFolderChannelAdapter(resumes_folder)],
        extraction_service=ExtractionService(),
        dedup_service=IdentityDedupService(),
        manual_review_queue=manual_review_queue,
        audit_log=audit_log,
        text_log=text_log,
    )

    results: list[CandidateResult] = []
    for candidate, extracted in gateway.run_once():
        profile = build_candidate_profile(extracted)
        score = ScoringEngine().score(profile, jrp, extracted.parser_version)
        results.append(CandidateResult(candidate=candidate, extracted=extracted, score=score))

    results.sort(key=lambda result: result.score.total_score, reverse=True)
    return results, manual_review_queue


_CONTROL_CHAR_PATTERN = re.compile("[\x00-\x1f\x7f]")
"""Every ASCII C0 control character (including ESC, \\x1b -- the lead-in byte of every ANSI escape
sequence) plus DEL. Newline/carriage-return alone were stripped before, but a candidate name is
untrusted submission data (a message envelope's display name, once a real Email/Teams adapter is
built), and a name crafted with a raw ANSI escape sequence (e.g. screen-clear + fake green "all
candidates passed" text) survived unstripped -- terminal output spoofing distinct from, but the
same class of risk as, the newline-forged-second-row case this function already guarded against."""


def candidate_label(candidate: Candidate) -> str:
    """A human-readable identifier for display -- falls back through email/phone/candidate_id
    when no name is on file. Every control character (newlines included) is replaced with a
    space: this ultimately comes from untrusted submission data, and a label containing one could
    otherwise forge what looks like a second, standalone entry in a printed report or table, or
    inject raw terminal escape sequences into console output."""
    raw_label = candidate.name or candidate.email or candidate.phone or candidate.candidate_id
    return _CONTROL_CHAR_PATTERN.sub(" ", raw_label)
