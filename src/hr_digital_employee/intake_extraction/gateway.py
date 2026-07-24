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
    Candidate,
    ExtractedResume,
    ManualReviewItem,
    MatchOutcome,
    QueueReason,
    RawSubmission,
)
from hr_digital_employee.intake_extraction.pdf_text import extract_text
from hr_digital_employee.intake_extraction.text_extraction_log import TextExtractionLog

_NO_PARSER_VERSION = "n/a"
"""Stamped on manual-review audit events raised before extraction ever ran (unparseable file,
suspected injection, ambiguous identity) -- there is no parser output to version in those cases."""

_MANUAL_REVIEW_AUDIT_ACTION: dict[QueueReason, str] = {
    QueueReason.UNPARSEABLE_FILE: "unparseable_file_flagged",
    QueueReason.SUSPECTED_INJECTION: "suspected_injection_flagged",
    QueueReason.LOW_CONFIDENCE_MUST_HAVE: "low_confidence_must_have_flagged",
    QueueReason.AMBIGUOUS_IDENTITY_MATCH: "ambiguous_identity_match_flagged",
    QueueReason.PROCESSING_ERROR: "processing_error_flagged",
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
        text_log: TextExtractionLog | None = None,
    ) -> None:
        self._channel_adapters = channel_adapters
        self._extraction_service = extraction_service
        self._dedup_service = dedup_service
        self._manual_review_queue = manual_review_queue
        self._audit_log = audit_log
        self._text_log = text_log

    def run_once(self) -> list[tuple[Candidate, ExtractedResume]]:
        """Fetch new submissions from every channel and process each one.

        One malformed submission (e.g. a corrupted PDF pypdf can't even partially parse) must not
        abort the whole batch and silently drop every submission queued after it -- anything that
        escapes `_process_submission`'s own known-shape handling is caught here and routed to
        manual review the same way, rather than left to propagate and crash `run_once()` itself.
        """
        results: list[tuple[Candidate, ExtractedResume]] = []
        for adapter in self._channel_adapters:
            for submission in adapter.fetch_new_submissions():
                try:
                    result = self._process_submission(submission)
                except Exception as error:
                    self._route_to_manual_review(
                        submission,
                        QueueReason.PROCESSING_ERROR,
                        f"{type(error).__name__}: {error}",
                    )
                    continue
                if result is not None:
                    results.append(result)
        return results

    def _process_submission(
        self, submission: RawSubmission
    ) -> tuple[Candidate, ExtractedResume] | None:
        extraction_result = extract_text(submission.file_bytes)
        if extraction_result is None:
            self._route_to_manual_review(
                submission, QueueReason.UNPARSEABLE_FILE, "unparseable file"
            )
            return None
        raw_text, ocr_confidence = extraction_result

        screening = screen(raw_text)
        if screening.suspected_injection:
            self._route_to_manual_review(
                submission,
                QueueReason.SUSPECTED_INJECTION,
                ", ".join(screening.matched_patterns),
            )
            return None

        if self._text_log is not None:
            self._text_log.append(submission, screening.cleaned_text)

        extracted = self._extraction_service.extract(screening.cleaned_text, ocr_confidence)
        if self._has_low_confidence_must_have(extracted):
            self._route_to_manual_review(
                submission,
                QueueReason.LOW_CONFIDENCE_MUST_HAVE,
                "must-have field below confidence threshold",
                version=extracted.parser_version,
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
        # Deliberately NOT wrapped in try/except (unlike _route_to_manual_review's audit write
        # below) -- confirmed via test_an_audit_log_failure_during_manual_review_routing_does_
        # not_crash_the_batch that this is an intentional, already-considered choice, not an
        # oversight: if the audit backend is down, an otherwise-clean candidate's own
        # "resume_processed" event failing to record propagates out, is caught by run_once()'s
        # exception boundary, and correctly redirects this candidate to manual review too, rather
        # than letting it through to the final ranked results with no audit trail at all ("nothing
        # should be silently marked processed with no audit trail" -- see that test's docstring and
        # design.md's "everything auditable" principle). Making this best-effort like the manual-
        # review path would violate that invariant for exactly the outcome (a candidate reaching a
        # human-facing ranked report) where an audit trail matters most.
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
        # A field that's UNVERIFIED (section missing entirely) never "meets" the threshold either
        # -- it must route to manual review just like a low-confidence VERIFIED field, not sail
        # through unflagged (design.md §3.2, FR-3).
        return any(
            not candidate_field.meets_must_have_confidence
            for candidate_field in (extracted.skills, extracted.experience)
        )

    def _route_to_manual_review(
        self,
        submission: RawSubmission,
        reason: QueueReason,
        detail: str,
        version: str = _NO_PARSER_VERSION,
    ) -> None:
        # The audit write is best-effort here, not load-bearing for the enqueue below: an audit
        # backend failure (a locked/unavailable database, most plausibly two HR staff running the
        # CLI/dashboard concurrently against the same --audit-db file) previously propagated
        # straight out of this method, uncaught -- crashing run_once() entirely and dropping this
        # submission from BOTH the audit log and the manual-review queue, along with every other
        # already-processed result in the same batch. Manual review exists precisely to catch
        # cases automation can't handle cleanly; a downed audit backend must not also cost the
        # submission its own safety net. The missing audit trail entry in that case is a known,
        # accepted gap (see ASSUMPTIONS.md) -- there is no secondary logging channel in this system
        # to fall back to.
        try:
            self._audit_log.record(
                AuditEvent(
                    actor="ingestion_gateway",
                    entity_ref=submission.display_identifier,
                    action=_MANUAL_REVIEW_AUDIT_ACTION[reason],
                    reason=detail,
                    timestamp=datetime.now(UTC),
                    version=version,
                )
            )
        except Exception:  # see comment above: must not block the enqueue below
            pass
        self._manual_review_queue.enqueue(
            ManualReviewItem(
                submission=submission,
                reason=reason,
                detail=detail,
                queued_at=datetime.now(UTC),
            )
        )
