"""Retention/deletion eligibility (FR-23) -- pure, testable eligibility checks.

The recurring scheduled job that actually deletes/anonymizes eligible records is Module 7's job
(module-4 doc §5: "coordinates with Module 7") -- this module defines *when* something becomes
eligible, not the recurring infrastructure that acts on it (that needs a real job scheduler, the
same kind of gap as Module 1's malware scanning; see ASSUMPTIONS.md).
"""

from __future__ import annotations

from datetime import datetime, timedelta

DEFAULT_RETENTION_MONTHS = 24
"""FR-23: non-hired candidate data auto-deletes/anonymizes at this many months by default."""

WITHDRAWAL_DELETION_DAYS = 30
"""FR-23: consent withdrawal triggers deletion within this many days."""

_DAYS_PER_MONTH = 30
"""A calendar-month approximation -- see ASSUMPTIONS.md."""


def is_eligible_for_routine_deletion(
    last_activity_at: datetime, now: datetime, retention_months: int = DEFAULT_RETENTION_MONTHS
) -> bool:
    threshold = last_activity_at + timedelta(days=retention_months * _DAYS_PER_MONTH)
    return now >= threshold


def is_eligible_for_withdrawal_deletion(withdrawn_at: datetime, now: datetime) -> bool:
    return now >= withdrawn_at + timedelta(days=WITHDRAWAL_DELETION_DAYS)
