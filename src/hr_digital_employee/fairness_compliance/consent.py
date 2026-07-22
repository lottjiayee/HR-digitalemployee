"""Consent capture (FR-22): a PICS notice at intake, and talent-pool consent kept separate and
unbundled from application consent -- granting one never implies the other.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from hr_digital_employee.fairness_compliance.models import ConsentRecord, ConsentType
from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog

PICS_NOTICE = (
    "This application will be screened using an automated system that extracts information from "
    "your resume and scores it against role requirements. A human reviewer makes all final "
    "decisions -- the system cannot reject or advance you on its own. You may request an "
    "explanation of your evaluation, and access to or correction of your personal data, at any "
    "time."
)
"""FR-22: the collection notice given to a candidate at intake (T4.5)."""


class ConsentService:
    """Records and withdraws consent per `ConsentType`, each tracked independently -- withdrawing
    talent-pool consent never touches application consent, and vice versa (T4.6)."""

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._records: dict[tuple[str, ConsentType], ConsentRecord] = {}

    def record_consent(
        self, candidate_id: str, consent_type: ConsentType, actor: str
    ) -> ConsentRecord:
        record = ConsentRecord(
            candidate_id=candidate_id, consent_type=consent_type, granted_at=datetime.now(UTC)
        )
        self._records[(candidate_id, consent_type)] = record
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref=candidate_id,
                action=f"consent_granted_{consent_type.value}",
                reason="candidate consent recorded at intake",
                timestamp=datetime.now(UTC),
                version="1",
            )
        )
        return record

    def withdraw_consent(
        self, candidate_id: str, consent_type: ConsentType, actor: str
    ) -> ConsentRecord:
        key = (candidate_id, consent_type)
        existing = self._records.get(key)
        if existing is None:
            raise ValueError(f"no {consent_type.value} consent on file for {candidate_id!r}")

        withdrawn = dataclasses.replace(existing, withdrawn_at=datetime.now(UTC))
        self._records[key] = withdrawn
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref=candidate_id,
                action=f"consent_withdrawn_{consent_type.value}",
                reason="candidate withdrew consent",
                timestamp=datetime.now(UTC),
                version="1",
            )
        )
        return withdrawn

    def has_active_consent(self, candidate_id: str, consent_type: ConsentType) -> bool:
        record = self._records.get((candidate_id, consent_type))
        return record is not None and record.withdrawn_at is None
