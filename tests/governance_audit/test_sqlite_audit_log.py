"""Tests for the SQLite-backed audit log (ASSUMPTIONS.md: Audit log persistence)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hr_digital_employee.governance_audit.models import AuditEvent
from hr_digital_employee.governance_audit.sqlite_audit_log import SqliteAuditLog


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
    log = SqliteAuditLog()
    log.record(_event("cand-1", "resume_processed"))
    log.record(_event("cand-2", "resume_processed"))

    assert len(log.all_events()) == 2


def test_events_for_filters_by_entity_ref() -> None:
    log = SqliteAuditLog()
    log.record(_event("cand-1", "resume_processed"))
    log.record(_event("cand-2", "resume_processed"))

    events = log.events_for("cand-1")

    assert len(events) == 1
    assert events[0].entity_ref == "cand-1"


def test_events_survive_reopening_the_same_file(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"

    first_connection = SqliteAuditLog(db_path)
    first_connection.record(_event("cand-1", "resume_processed"))
    first_connection.close()

    second_connection = SqliteAuditLog(db_path)
    events = second_connection.all_events()

    assert len(events) == 1
    assert events[0].entity_ref == "cand-1"
    assert events[0].action == "resume_processed"


def test_events_are_returned_in_the_order_they_were_recorded() -> None:
    log = SqliteAuditLog()
    log.record(_event("cand-1", "first_action"))
    log.record(_event("cand-1", "second_action"))

    events = log.events_for("cand-1")

    assert [e.action for e in events] == ["first_action", "second_action"]


def test_timestamp_round_trips_exactly_for_a_timezone_aware_datetime() -> None:
    log = SqliteAuditLog()
    original = _event("cand-1", "resume_processed")

    log.record(original)

    assert log.all_events()[0].timestamp == original.timestamp


def test_timestamp_round_trips_without_shifting_a_naive_datetime() -> None:
    # Regression test: a naive datetime must come back with the identical wall-clock value, not
    # silently reinterpreted through the local system timezone.
    log = SqliteAuditLog()
    naive_event = AuditEvent(
        actor="test",
        entity_ref="cand-1",
        action="resume_processed",
        reason="unit test",
        timestamp=datetime(2026, 7, 21, 12, 0, 0),  # deliberately naive, no tzinfo
        version="1.0",
    )

    log.record(naive_event)

    assert log.all_events()[0].timestamp == naive_event.timestamp


def test_an_incompatible_existing_schema_fails_at_construction_not_on_first_record(
    tmp_path: Path,
) -> None:
    # Regression (round 6): `CREATE TABLE IF NOT EXISTS` silently no-ops against a pre-existing
    # `audit_events` table with a different schema -- the incompatibility used to go unnoticed
    # until the first real record() call, deep inside the processing pipeline. Once gateway-level
    # code started tolerating a record() failure as presumed-transient (to avoid one bad audit
    # write crashing an entire batch), a *permanent* incompatibility needed to surface earlier, at
    # construction, or it would go completely unreported.
    db_path = tmp_path / "incompatible.db"
    connection = sqlite3.connect(str(db_path))
    connection.execute(
        "CREATE TABLE audit_events (id INTEGER PRIMARY KEY, actor TEXT, entity_ref TEXT, "
        "action TEXT, reason TEXT, timestamp TEXT)"  # missing the "version" column
    )
    connection.commit()
    connection.close()

    with pytest.raises(sqlite3.OperationalError, match="version"):
        SqliteAuditLog(db_path)
