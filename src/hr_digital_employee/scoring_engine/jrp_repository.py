"""JRP storage with change auditing (module-2-scoring-engine.md §4: "every JRP weight/threshold/
must-have change is audit-logged (actor, timestamp, reason) -- feeds Module 7").
"""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog
from hr_digital_employee.scoring_engine.models import JRP, weight_guideline_warnings


class JRPRepository:
    """In-memory JRP store, keyed by `jrp_id`, holding only the current version of each. A real
    deployment would keep every prior version queryable (NFR-5 "one hiring round = one version"
    needs old versions retrievable) -- this stub keeps the audit trail but not a version history
    table; see ASSUMPTIONS.md.
    """

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._jrps: dict[str, JRP] = {}

    def save(self, jrp: JRP, actor: str, reason: str) -> None:
        self._jrps[jrp.jrp_id] = jrp
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref=jrp.jrp_id,
                action="jrp_saved",
                reason=reason,
                timestamp=datetime.now(UTC),
                version=str(jrp.version),
            )
        )
        for warning in weight_guideline_warnings(jrp):
            self._audit_log.record(
                AuditEvent(
                    actor=actor,
                    entity_ref=jrp.jrp_id,
                    action="jrp_weight_guideline_warning",
                    reason=warning,
                    timestamp=datetime.now(UTC),
                    version=str(jrp.version),
                )
            )

    def get(self, jrp_id: str) -> JRP | None:
        return self._jrps.get(jrp_id)
