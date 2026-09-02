"""Optional analysis history, backed by SQLite.

Disabled by default (``PGPA_HISTORY_ENABLED=false``) so pgPlanAdvisor stays
a stateless service unless an operator opts in. When enabled, a successful
``POST /api/v1/analyze`` with ``"save": true`` is persisted here and becomes
retrievable via ``GET /api/v1/history``. Uses the stdlib ``sqlite3`` module
rather than an ORM to keep the dependency footprint of a "focused" upgrade
small - this is a lookup table, not a data model that needs migrations.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import Settings
from app.models import AnalyzeResponse, HistoryListItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    label TEXT,
    summary TEXT NOT NULL,
    total_runtime_ms REAL NOT NULL,
    top_severity TEXT,
    finding_count INTEGER NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at DESC);
"""


class HistoryStore:
    def __init__(self, db_path: str, max_rows: int) -> None:
        self.db_path = db_path
        self.max_rows = max_rows
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, result: AnalyzeResponse) -> None:
        top_severity = result.top_findings[0].severity.value if result.top_findings else None
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO analyses "
                "(id, created_at, label, summary, total_runtime_ms, top_severity, finding_count, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.id,
                    result.created_at.isoformat(),
                    result.label,
                    result.summary,
                    result.total_runtime_ms,
                    top_severity,
                    len(result.top_findings),
                    result.model_dump_json(),
                ),
            )
            # Trim oldest rows beyond max_rows to keep this bounded on a
            # long-running, never-restarted instance.
            conn.execute(
                "DELETE FROM analyses WHERE id NOT IN "
                "(SELECT id FROM analyses ORDER BY created_at DESC LIMIT ?)",
                (self.max_rows,),
            )

    def list(self, limit: int = 50, offset: int = 0) -> tuple[list[HistoryListItem], int]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) AS c FROM analyses").fetchone()["c"]
            rows = conn.execute(
                "SELECT id, created_at, label, summary, total_runtime_ms, top_severity, finding_count "
                "FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        items = [
            HistoryListItem(
                id=r["id"],
                created_at=r["created_at"],
                label=r["label"],
                summary=r["summary"],
                total_runtime_ms=r["total_runtime_ms"],
                top_severity=r["top_severity"],
                finding_count=r["finding_count"],
            )
            for r in rows
        ]
        return items, total

    def get(self, analysis_id: str) -> AnalyzeResponse | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT payload FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if row is None:
            return None
        return AnalyzeResponse.model_validate(json.loads(row["payload"]))

    def delete(self, analysis_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cur.rowcount > 0


_store: HistoryStore | None = None


def get_history_store(settings: Settings) -> HistoryStore | None:
    global _store
    if not settings.history_enabled:
        return None
    if _store is None or _store.db_path != settings.history_db_path:
        _store = HistoryStore(settings.history_db_path, settings.history_max_rows)
    return _store
