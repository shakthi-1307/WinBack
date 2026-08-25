"""
The event ledger — the Clerk's notebook, written in pen.

Append-only. There is no update method and no delete method, and that is not
an oversight. A transaction's history is reconstructed by replaying its
events in order, so any story the ledger tells can be checked against the
same events that produced it.

SQLite rather than Postgres, on purpose: the whole system has to run from
`docker compose up` with no external services, and nothing here needs
concurrent writers. The schema moves to Postgres unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT    NOT NULL,
    strategy   TEXT    NOT NULL,
    day        INTEGER NOT NULL,
    txn_id     TEXT    NOT NULL,
    type       TEXT    NOT NULL,
    payload    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_txn ON events(run_id, txn_id, seq);
"""

# Every kind of thing that can happen. Adding a case here is how you extend
# the system; there is no other way to record anything.
PLANNED = "planned"
BLOCKED = "blocked"
EXECUTED = "executed"
DUPLICATE_SUPPRESSED = "duplicate_suppressed"
GATEWAY_ERROR = "gateway_error"
RECOVERED = "recovered"
ABANDONED = "abandoned"
HOSTILE_NOTE = "hostile_note_seen"


@dataclass
class Ledger:
    path: str = ":memory:"
    run_id: str = "run"
    strategy: str = ""

    def __post_init__(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- writing (the only mutation the ledger permits) -----------------

    def append(self, day: int, txn_id: str, type_: str, **payload: Any) -> None:
        self._conn.execute(
            "INSERT INTO events (run_id, strategy, day, txn_id, type, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (self.run_id, self.strategy, day, txn_id, type_, json.dumps(payload, default=str)),
        )

    def commit(self) -> None:
        self._conn.commit()

    # -- reading --------------------------------------------------------

    def events_for(self, txn_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT seq, day, type, payload FROM events "
            "WHERE run_id = ? AND txn_id = ? ORDER BY seq",
            (self.run_id, txn_id),
        ).fetchall()
        return [
            {"seq": r[0], "day": r[1], "type": r[2], **json.loads(r[3])} for r in rows
        ]

    def counts_by_type(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) FROM events WHERE run_id = ? GROUP BY type "
            "ORDER BY COUNT(*) DESC",
            (self.run_id,),
        ).fetchall()
        return dict(rows)

    def total(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ?", (self.run_id,)
        ).fetchone()[0]

    def transactions_with(self, type_: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT txn_id FROM events WHERE run_id = ? AND type = ?",
            (self.run_id, type_),
        ).fetchall()
        return [r[0] for r in rows]
