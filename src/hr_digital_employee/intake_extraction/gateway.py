"""Ingestion Gateway: orchestrates intake -> screening -> extraction -> dedup (SOP 2.1, 5.1)."""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog
from hr_digital_employee.intake_extraction.channel_adapters import ChannelAdapter
from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.injection_screening import screen
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.models import (
    MUST_HAVE_CONFIDENCE_THRESHOLD,
    Candidate,
    ExtractedResume,
    FieldStatus,
    ManualReviewItem,
    MatchOutcome,
    QueueReason,
    RawSubmission,
)
from hr_digital_employee.intake_extraction.pdf_text import extract_text

_MANUAL_REVIEW_AUDIT_ACTION: dict[QueueReason, str] = {
    QueueReason.UNPARSEABLE_FILE: "unparseable_file_flagged",
    QueueReason.SUSPECTED_INJECTION: "suspected_injection_flagged",
    QueueReason.LOW_CONFIDENCE_MUST_HAVE: "low_confidence_must_have_flagged",
    QueueReason.AMBIGUOUS_IDENTITY_MATCH: "ambiguous_identity_match_flagged",
}
"""Module 7 requires every decision-relevant routing outcome logged -- one action name per
QueueReason keeps existing audit consumers (e.g. the injection flag) stable while covering the
other three routing reasons, which previously reached the manual-review queue with no audit
event at all."""


class IngestionGateway:
    """Coordinates channel intake, screening, extraction, and dedup for one processing pass."""

    def __init__(
        self,
        channel_adapters: list[ChannelAdapter],
        extraction_service: ExtractionService,
        dedup_service: IdentityDedupService,
        manual_review_queue: ManualReviewQueue,
        audit_log: AuditLog,
    ) -> None:
        self._channel_adapters = channel_adapters
        self._extraction_service = extraction_service
        self._dedup_service = dedup_service
        self._manual_review_queue = manual_review_queue
        self._audit_log = audit_log

    def run_once(self) -> list[tuple[Candidate, ExtractedResume]]:
        """Fetch new submissions from every channel and process each one."""
        results: list[tuple[Candidate, ExtractedResume]] = []
        for adapter in self._channel_adapters:
            for submission in adapter.fetch_new_submissions():
                result = self._process_submission(submission)
                if result is not None:
                    results.append(result)
        return results

    def _process_submission(
        self, submission: RawSubmission
    ) -> tuple[Candidate, ExtractedResume] | None:
        raw_text = extract_text(submission.file_bytes)
        if raw_text is None:
            self._route_to_manual_review(
                submission, QueueReason.UNPARSEABLE_FILE, "unparseable file"
            )
            return None

        screening = screen(raw_text)
        if screening.suspected_injection:
            self._route_to_manual_review(
                submission,
                QueueReason.SUSPECTED_INJECTION,
                ", ".join(screening.matched_patterns),
            )
            return None

        extracted = self._extraction_service.extract(screening.cleaned_text)
        if self._has_low_confidence_must_have(extracted):
            self._route_to_manual_review(
                submission,
                QueueReason.LOW_CONFIDENCE_MUST_HAVE,
                "must-have field below confidence threshold",
            )
            return None

        match = self._dedup_service.match(submission)
        if match.outcome is MatchOutcome.AMBIGUOUS:
            self._route_to_manual_review(
                submission, QueueReason.AMBIGUOUS_IDENTITY_MATCH, "ambiguous identity match"
            )
            return None

        candidate = match.candidate
        assert candidate is not None  # NEW_PROFILE / MERGED_INTO_EXISTING always set this
        self._audit_log.record(
            AuditEvent(
                actor="ingestion_gateway",
                entity_ref=candidate.candidate_id,
                action="resume_processed",
                reason=match.outcome.value,
                timestamp=datetime.now(UTC),
                version=extracted.parser_version,
            )
        )
        return candidate, extracted

    def _has_low_confidence_must_have(self, extracted: ExtractedResume) -> bool:
        # Skills and Experience stand in here for "fields a JRP might mark must-have" -- the
        # real must-have determination is JRP-specific and lives in Module 2 (Scoring Engine).
        for candidate_field in (extracted.skills, extracted.experience):
            if (
                candidate_field.status is FieldStatus.VERIFIED
                and candidate_field.confidence < MUST_HAVE_CONFIDENCE_THRESHOLD
            ):
                return True
        return False

    def _route_to_manual_review(
        self, submission: RawSubmission, reason: QueueReason, detail: str
    ) -> None:
        self._audit_log.record(
            AuditEvent(
                actor="ingestion_gateway",
                entity_ref=submission.candidate_email or submission.candidate_phone or "unknown",
                action=_MANUAL_REVIEW_AUDIT_ACTION[reason],
                reason=detail,
                timestamp=datetime.now(UTC),
                version="1.0",
            )
        )
        self._manual_review_queue.enqueue(
            ManualReviewItem(
                submission=submission,
                reason=reason,
                detail=detail,
                queued_at=datetime.now(UTC),
            )
        )
