"""Tests for the manual-review queue (SOP 2.1.1, 2.1.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.models import (
    ManualReviewItem,
    QueueReason,
    RawSubmission,
    SubmissionChannel,
)


def _item(reason: QueueReason) -> ManualReviewItem:
    submission = RawSubmission(
        channel=SubmissionChannel.EMAIL,
        candidate_email=None,
        candidate_phone=None,
        candidate_name=None,
        file_bytes=b"",
        received_at=datetime.now(UTC),
    )
    return ManualReviewItem(
        submission=submission,
        reason=reason,
        detail="test",
        queued_at=datetime.now(UTC),
    )


def test_enqueue_and_retrieve_items() -> None:
    queue = ManualReviewQueue()
    queue.enqueue(_item(QueueReason.UNPARSEABLE_FILE))
    queue.enqueue(_item(QueueReason.SUSPECTED_INJECTION))

    assert len(queue) == 2
    reasons = [item.reason for item in queue.items()]
    assert reasons == [QueueReason.UNPARSEABLE_FILE, QueueReason.SUSPECTED_INJECTION]
