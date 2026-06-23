"""CostTracker 窶・records every LLM call and provides cost summaries."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Generator


@dataclass
class CostRecord:
    provider_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    status: str = "success"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    run_id: str | None = None
    task_type: str | None = None
    error_type: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ProviderCostSummary:
    provider_name: str
    total_cost_usd: float
    total_calls: int
    total_tokens: int
    avg_duration_ms: float


@dataclass
class CostSummary:
    total_cost_usd: float
    total_calls: int
    total_tokens: int
    by_provider: dict[str, ProviderCostSummary] = field(default_factory=dict)
    by_task_type: dict[str, float] = field(default_factory=dict)


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS cost_records (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'success',
    run_id TEXT,
    task_type TEXT,
    error_type TEXT
)
"""


class CostTracker:
    """SQLite-backed cost tracker. Thread-safe via per-call connections."""

    def __init__(self, db_path: str | Path = "platform.db") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(_CREATE_SQL)

    def record(self, record: CostRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO cost_records
                  (id, timestamp, provider_name, model,
                   input_tokens, output_tokens, cost_usd, duration_ms,
                   status, run_id, task_type, error_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.id,
                    record.timestamp.isoformat(),
                    record.provider_name,
                    record.model,
                    record.input_tokens,
                    record.output_tokens,
                    record.cost_usd,
                    record.duration_ms,
                    record.status,
                    record.run_id,
                    record.task_type,
                    record.error_type,
                ),
            )

    def get_summary(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        provider: str | None = None,
    ) -> CostSummary:
        conditions: list[str] = []
        params: list[object] = []
        if start:
            conditions.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            conditions.append("timestamp <= ?")
            params.append(end.isoformat())
        if provider:
            conditions.append("provider_name = ?")
            params.append(provider)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._conn() as conn:
            row = conn.execute(
                f"SELECT SUM(cost_usd), COUNT(*), SUM(input_tokens + output_tokens) "
                f"FROM cost_records {where}",
                params,
            ).fetchone()
            total_cost = row[0] or 0.0
            total_calls = row[1] or 0
            total_tokens = row[2] or 0

            by_provider_rows = conn.execute(
                f"""
                SELECT provider_name,
                       SUM(cost_usd) as cost,
                       COUNT(*) as calls,
                       SUM(input_tokens + output_tokens) as tokens,
                       AVG(duration_ms) as avg_dur
                FROM cost_records {where}
                GROUP BY provider_name
                """,
                params,
            ).fetchall()

            task_conditions = conditions + ["task_type IS NOT NULL"]
            task_where = "WHERE " + " AND ".join(task_conditions)
            by_task_rows = conn.execute(
                f"""
                SELECT task_type, SUM(cost_usd) as cost
                FROM cost_records {task_where}
                GROUP BY task_type
                """,
                params,
            ).fetchall()

        by_provider = {
            r["provider_name"]: ProviderCostSummary(
                provider_name=r["provider_name"],
                total_cost_usd=r["cost"] or 0.0,
                total_calls=r["calls"] or 0,
                total_tokens=r["tokens"] or 0,
                avg_duration_ms=r["avg_dur"] or 0.0,
            )
            for r in by_provider_rows
        }
        by_task_type = {r["task_type"]: r["cost"] or 0.0 for r in by_task_rows}

        return CostSummary(
            total_cost_usd=total_cost,
            total_calls=total_calls,
            total_tokens=total_tokens,
            by_provider=by_provider,
            by_task_type=by_task_type,
        )

    def get_today_cost(self) -> float:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_summary(start=today).total_cost_usd
