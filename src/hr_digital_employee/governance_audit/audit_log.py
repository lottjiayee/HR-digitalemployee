"""In-memory append-only audit log (stub -- see ASSUMPTIONS.md for real persistence)."""

from __future__ import annotations

from hr_digital_employee.governance_audit.models import AuditEvent


class InMemoryAuditLog:
    """Append-only audit log. A real deployment persists this durably and separately from
    application data (SOP 4.3 layered retention) -- this stub keeps other modules testable
    without a database dependency. See ASSUMPTIONS.md.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    def events_for(self, entity_ref: str) -> list[AuditEvent]:
        return [e for e in self._events if e.entity_ref == entity_ref]

    def all_events(self) -> list[AuditEvent]:
        return list(self._events)
