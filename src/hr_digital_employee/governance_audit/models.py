"""Audit event model (SOP 1.6, 2.2.5, 6.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditEvent:
    """One decision-relevant event. Every module that produces a decision-relevant output emits
    one of these through the shared AuditLog interface -- never an ad hoc log line."""

    actor: str
    entity_ref: str
    action: str
    reason: str
    timestamp: datetime
    version: str
