"""Tests for consent capture (FR-22, test.md T4.5-T4.6)."""

from __future__ import annotations

import pytest

from hr_digital_employee.fairness_compliance.consent import PICS_NOTICE, ConsentService
from hr_digital_employee.fairness_compliance.models import ConsentType
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog


def test_t4_5_pics_notice_explains_automated_screening_and_human_decisioning() -> None:
    assert "automated" in PICS_NOTICE.lower()
    assert "human" in PICS_NOTICE.lower()


def test_t4_6_talent_pool_and_application_consent_are_tracked_separately() -> None:
    service = ConsentService(InMemoryAuditLog())

    service.record_consent("cand-1", ConsentType.APPLICATION, actor="cand-1")

    assert service.has_active_consent("cand-1", ConsentType.APPLICATION) is True
    assert service.has_active_consent("cand-1", ConsentType.TALENT_POOL) is False


def test_withdrawing_talent_pool_consent_does_not_affect_application_consent() -> None:
    service = ConsentService(InMemoryAuditLog())
    service.record_consent("cand-1", ConsentType.APPLICATION, actor="cand-1")
    service.record_consent("cand-1", ConsentType.TALENT_POOL, actor="cand-1")

    service.withdraw_consent("cand-1", ConsentType.TALENT_POOL, actor="cand-1")

    assert service.has_active_consent("cand-1", ConsentType.APPLICATION) is True
    assert service.has_active_consent("cand-1", ConsentType.TALENT_POOL) is False


def test_withdraw_raises_if_no_consent_was_ever_recorded() -> None:
    service = ConsentService(InMemoryAuditLog())

    with pytest.raises(ValueError, match="no talent_pool consent on file"):
        service.withdraw_consent("cand-1", ConsentType.TALENT_POOL, actor="cand-1")


def test_consent_grant_and_withdrawal_are_audit_logged() -> None:
    audit_log = InMemoryAuditLog()
    service = ConsentService(audit_log)

    service.record_consent("cand-1", ConsentType.APPLICATION, actor="cand-1")
    service.withdraw_consent("cand-1", ConsentType.APPLICATION, actor="cand-1")

    actions = [e.action for e in audit_log.events_for("cand-1")]
    assert actions == ["consent_granted_application", "consent_withdrawn_application"]
