"""Tests for the access/correction request workflow (FR-26, test.md T4.12)."""

from __future__ import annotations

import pytest

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


def test_a_fulfilled_request_cannot_be_regressed_back_to_received() -> None:
    # Regression (round 6): advance() had no state-machine validation at all -- a FULFILLED
    # request could be silently regressed to any other status, undermining the reliability of the
    # compliance record for whether an FR-26 request was actually completed.
    service = AccessRequestService(InMemoryAuditLog())
    request = service.submit("cand-1", AccessRequestKind.ACCESS)
    service.advance(
        request.request_id, AccessRequestStatus.FULFILLED, actor="hr_alice", reason="done"
    )

    with pytest.raises(ValueError, match="lifecycle only moves forward"):
        service.advance(
            request.request_id, AccessRequestStatus.RECEIVED, actor="hr_alice", reason="oops"
        )


def test_advancing_to_the_same_status_again_is_rejected() -> None:
    service = AccessRequestService(InMemoryAuditLog())
    request = service.submit("cand-1", AccessRequestKind.ACCESS)
    service.advance(
        request.request_id, AccessRequestStatus.IN_PROGRESS, actor="hr_alice", reason="reviewing"
    )

    with pytest.raises(ValueError, match="lifecycle only moves forward"):
        service.advance(
            request.request_id, AccessRequestStatus.IN_PROGRESS, actor="hr_alice", reason="again"
        )


def test_advancing_an_unknown_request_id_raises_a_clean_error_not_a_raw_keyerror() -> None:
    # Regression: `self._requests[request_id]` with no bounds check raised an uncaught KeyError --
    # this service's own in-memory store is wiped on every process restart (module docstring), so
    # any caller looking up a request by a stale/typo'd id after a restart crashed ungracefully
    # instead of getting a clean, actionable error.
    service = AccessRequestService(InMemoryAuditLog())

    with pytest.raises(ValueError, match="no access request found"):
        service.advance(
            "does-not-exist", AccessRequestStatus.IN_PROGRESS, actor="hr_admin", reason="test"
        )


class _AlwaysFailsAuditLog:
    """Stands in for a real audit backend being unavailable (e.g. a locked SQLite file from a
    second concurrent process) -- every `record()` call raises."""

    def record(self, event: object) -> None:
        raise RuntimeError("simulated audit backend failure")

    def events_for(self, entity_ref: str) -> list[object]:
        return []

    def all_events(self) -> list[object]:
        return []


def test_submit_still_succeeds_when_the_audit_backend_is_down() -> None:
    # Regression: audit_log.record() had no exception boundary in submit() -- a transient audit
    # backend outage meant a candidate's legally-mandated FR-26 request was already stored in
    # self._requests but the exception still propagated out of submit(), so the caller had no way
    # to know the request actually went through (no request_id returned) and would plausibly
    # resubmit into a duplicate.
    service = AccessRequestService(_AlwaysFailsAuditLog())  # type: ignore[arg-type]

    request = service.submit("cand-1", AccessRequestKind.ACCESS)  # must not raise

    assert request.status is AccessRequestStatus.RECEIVED
    assert service.requests_for("cand-1") == [request]


def test_advance_still_succeeds_when_the_audit_backend_is_down() -> None:
    service = AccessRequestService(_AlwaysFailsAuditLog())  # type: ignore[arg-type]
    request = service.submit("cand-1", AccessRequestKind.ACCESS)

    updated = service.advance(  # must not raise
        request.request_id, AccessRequestStatus.IN_PROGRESS, actor="hr_alice", reason="reviewing"
    )

    assert updated.status is AccessRequestStatus.IN_PROGRESS


def test_every_transition_is_audit_logged() -> None:
    audit_log = InMemoryAuditLog()
    service = AccessRequestService(audit_log)
    request = service.submit("cand-1", AccessRequestKind.ACCESS)

    service.advance(
        request.request_id, AccessRequestStatus.FULFILLED, actor="hr_alice", reason="done"
    )

    actions = [e.action for e in audit_log.events_for("cand-1")]
    assert actions == ["access_request_received", "access_request_fulfilled"]
