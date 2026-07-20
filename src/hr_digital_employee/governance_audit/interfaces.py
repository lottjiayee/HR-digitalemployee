"""Public interface Module 7 exposes downstream -- every other module logs through this."""

from __future__ import annotations

from typing import Protocol

from hr_digital_employee.governance_audit.models import AuditEvent

__all__ = ["AuditEvent", "AuditLog"]


class AuditLog(Protocol):
    """Append-only, decision-relevant event log every module writes through (SOP 1.6)."""

    def record(self, event: AuditEvent) -> None: ...

    def events_for(self, entity_ref: str) -> list[AuditEvent]: ...
