"""Tests for the access/correction request workflow (FR-26, test.md T4.12)."""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.access_requests import AccessRequestService
from hr_digital_employee.fairness_compliance.models import AccessRequestKind, AccessRequestStatus
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog


def test_t4_12_a_submitted_request_starts_as_received() -> None:
    service = AccessRequestService(InMemoryAuditLog())

    request = service.submit("cand-1", AccessRequestKind.ACCESS)

    assert request.status is AccessRequestStatus.RECEIVED
    assert request.kind is AccessRequestKind.ACCESS


def test_a_request_can_be_advanced_through_its_lifecycle() -> None:
    service = AccessRequestService(InMemoryAuditLog())
    request = service.submit("cand-1", AccessRequestKind.CORRECTION)

    in_progress = service.advance(
        request.request_id, AccessRequestStatus.IN_PROGRESS, actor="hr_alice", reason="reviewing"
    )
    fulfilled = service.advance(
        request.request_id, AccessRequestStatus.FULFILLED, actor="hr_alice", reason="corrected"
    )

    assert in_progress.status is AccessRequestStatus.IN_PROGRESS
    assert fulfilled.status is AccessRequestStatus.FULFILLED


def test_requests_for_filters_by_candidate() -> None:
    service = AccessRequestService(InMemoryAuditLog())
    service.submit("cand-1", AccessRequestKind.ACCESS)
    service.submit("cand-2", AccessRequestKind.ACCESS)

    assert len(service.requests_for("cand-1")) == 1


def test_every_transition_is_audit_logged() -> None:
    audit_log = InMemoryAuditLog()
    service = AccessRequestService(audit_log)
    request = service.submit("cand-1", AccessRequestKind.ACCESS)

    service.advance(
        request.request_id, AccessRequestStatus.FULFILLED, actor="hr_alice", reason="done"
    )

    actions = [e.action for e in audit_log.events_for("cand-1")]
    assert actions == ["access_request_received", "access_request_fulfilled"]
