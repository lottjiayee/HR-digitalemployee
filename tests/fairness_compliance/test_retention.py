"""Tests for retention/deletion eligibility (FR-23, test.md T4.7-T4.8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hr_digital_employee.fairness_compliance.retention import (
    is_eligible_for_routine_deletion,
    is_eligible_for_withdrawal_deletion,
)

_NOW = datetime(2026, 7, 22, tzinfo=UTC)


def test_t4_7_a_record_reaching_24_months_old_is_eligible_for_deletion() -> None:
    last_activity = _NOW - timedelta(days=24 * 30 + 1)

    assert is_eligible_for_routine_deletion(last_activity, _NOW) is True


def test_a_record_younger_than_24_months_is_not_eligible() -> None:
    last_activity = _NOW - timedelta(days=24 * 30 - 1)

    assert is_eligible_for_routine_deletion(last_activity, _NOW) is False


def test_retention_period_is_configurable() -> None:
    last_activity = _NOW - timedelta(days=12 * 30 + 1)

    assert is_eligible_for_routine_deletion(last_activity, _NOW, retention_months=12) is True


def test_t4_8_withdrawal_deletion_is_eligible_after_30_days() -> None:
    withdrawn_at = _NOW - timedelta(days=31)

    assert is_eligible_for_withdrawal_deletion(withdrawn_at, _NOW) is True


def test_withdrawal_deletion_is_not_yet_eligible_within_30_days() -> None:
    withdrawn_at = _NOW - timedelta(days=29)

    assert is_eligible_for_withdrawal_deletion(withdrawn_at, _NOW) is False
