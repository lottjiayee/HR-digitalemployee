"""Tests for the (stub) in-memory audit log (SOP 1.6, test.md §7)."""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.governance_audit.models import AuditEvent


def _event(entity_ref: str, action: str) -> AuditEvent:
    return AuditEvent(
        actor="test",
        entity_ref=entity_ref,
        action=action,
        reason="unit test",
        timestamp=datetime.now(UTC),
        version="1.0",
    )


def test_record_and_retrieve_all_events() -> None:
    log = InMemoryAuditLog()
    log.record(_event("cand-1", "resume_processed"))
    log.record(_event("cand-2", "resume_processed"))

    assert len(log.all_events()) == 2


def test_events_for_filters_by_entity_ref() -> None:
    log = InMemoryAuditLog()
    log.record(_event("cand-1", "resume_processed"))
    log.record(_event("cand-2", "resume_processed"))

    events = log.events_for("cand-1")

    assert len(events) == 1
    assert events[0].entity_ref == "cand-1"
