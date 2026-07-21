"""SQLite-backed audit log -- a temporary, lightweight way to survive a process restart without
committing to a cloud database vendor (design.md §10.1 is still open). Same shape as
`InMemoryAuditLog`; swap the constructor call, nothing else about the `AuditLog` protocol changes.
See ASSUMPTIONS.md.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from hr_digital_employee.governance_audit.models import AuditEvent

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    version TEXT NOT NULL
)
"""

_SELECT_COLUMNS = "actor, entity_ref, action, reason, timestamp, version"


class SqliteAuditLog:
    """Append-only audit log backed by a SQLite file (or `:memory:`, mainly for tests).

    Not the real deployment's data store (design.md §4.2/§10.1 are still open) -- this exists so
    the audit trail survives a process restart in the meantime, which an in-memory list cannot.
    """

    def __init__(self, path: Path | str = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.execute(_CREATE_TABLE)
        self._connection.commit()

    def record(self, event: AuditEvent) -> None:
        self._connection.execute(
            f"INSERT INTO audit_events ({_SELECT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.actor,
                event.entity_ref,
                event.action,
                event.reason,
                event.timestamp.isoformat(),
                event.version,
            ),
        )
        self._connection.commit()

    def events_for(self, entity_ref: str) -> list[AuditEvent]:
        rows = self._connection.execute(
            f"SELECT {_SELECT_COLUMNS} FROM audit_events WHERE entity_ref = ? ORDER BY id",
            (entity_ref,),
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def all_events(self) -> list[AuditEvent]:
        rows = self._connection.execute(
            f"SELECT {_SELECT_COLUMNS} FROM audit_events ORDER BY id"
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def close(self) -> None:
        self._connection.close()


def _row_to_event(row: tuple[str, str, str, str, str, str]) -> AuditEvent:
    actor, entity_ref, action, reason, timestamp, version = row
    return AuditEvent(
        actor=actor,
        entity_ref=entity_ref,
        action=action,
        reason=reason,
        timestamp=datetime.fromisoformat(timestamp).astimezone(UTC),
        version=version,
    )
