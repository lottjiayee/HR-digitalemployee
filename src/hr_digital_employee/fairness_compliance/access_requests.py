"""Access/correction request handling (FR-26) -- tracks the request *lifecycle*
(received -> in_progress -> fulfilled) and audit-logs every transition.

No real candidate-data store exists yet to fulfill against (Module 1 doesn't persist full PII
records beyond its in-memory dedup list) -- this is honestly scoped as a workflow skeleton, not a
data-mutation engine; see ASSUMPTIONS.md.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime

from hr_digital_employee.fairness_compliance.models import (
    AccessRequest,
    AccessRequestKind,
    AccessRequestStatus,
)
from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog


class AccessRequestService:
    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._requests: dict[str, AccessRequest] = {}

    def submit(
        self, candidate_id: str, kind: AccessRequestKind, detail: str = ""
    ) -> AccessRequest:
        request = AccessRequest(
            request_id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            kind=kind,
            status=AccessRequestStatus.RECEIVED,
            requested_at=datetime.now(UTC),
            detail=detail,
        )
        self._requests[request.request_id] = request
        self._audit_log.record(
            AuditEvent(
                actor=candidate_id,
                entity_ref=candidate_id,
                action=f"{kind.value}_request_received",
                reason=detail or f"candidate submitted a {kind.value} request",
                timestamp=datetime.now(UTC),
                version="1",
            )
        )
        return request

    def advance(
        self, request_id: str, new_status: AccessRequestStatus, actor: str, reason: str
    ) -> AccessRequest:
        existing = self._requests[request_id]
        updated = dataclasses.replace(existing, status=new_status)
        self._requests[request_id] = updated
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref=existing.candidate_id,
                action=f"{existing.kind.value}_request_{new_status.value}",
                reason=reason,
                timestamp=datetime.now(UTC),
                version="1",
            )
        )
        return updated

    def requests_for(self, candidate_id: str) -> list[AccessRequest]:
        return [r for r in self._requests.values() if r.candidate_id == candidate_id]
