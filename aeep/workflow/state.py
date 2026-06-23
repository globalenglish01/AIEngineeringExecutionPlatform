"""WorkflowRun state management with SQLite persistence and checkpoint resume."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator

from aeep.core.interfaces.workflow import NodeStatus


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class NodeRun:
    node_id: str
    run_id: str
    status: NodeStatus = NodeStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt: int = 1

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            delta = (self.completed_at - self.started_at).total_seconds()
            return int(delta * 1000)
        return None


@dataclass
class WorkflowRun:
    workflow_name: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    initial_context: dict[str, Any] = field(default_factory=dict)
    final_context: dict[str, Any] = field(default_factory=dict)
    node_runs: dict[str, NodeRun] = field(default_factory=dict)
    error: str | None = None

    def completed_nodes(self) -> set[str]:
        return {
            nr.node_id
            for nr in self.node_runs.values()
            if nr.status == NodeStatus.COMPLETED
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    initial_context TEXT,
    final_context TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS node_runs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    output TEXT,
    error TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_node_runs_run_id ON node_runs(run_id);
"""


class WorkflowStateStore:
    """SQLite-backed store for workflow and node run state."""

    def __init__(self, db_path: str | Path = "platform.db") -> None:
        self._db_path = str(db_path)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # WorkflowRun CRUD
    # ------------------------------------------------------------------

    def create_run(self, run: WorkflowRun) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO workflow_runs (run_id, workflow_name, status, started_at, initial_context) "
                "VALUES (?,?,?,?,?)",
                (
                    run.run_id,
                    run.workflow_name,
                    run.status.value,
                    run.started_at.isoformat(),
                    json.dumps(self._safe_json(run.initial_context)),
                ),
            )

    def update_run(self, run: WorkflowRun) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE workflow_runs SET status=?, completed_at=?, final_context=?, error=? "
                "WHERE run_id=?",
                (
                    run.status.value,
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(self._safe_json(run.final_context)),
                    run.error,
                    run.run_id,
                ),
            )

    def load_run(self, run_id: str) -> WorkflowRun | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                return None
            node_rows = conn.execute(
                "SELECT * FROM node_runs WHERE run_id=?", (run_id,)
            ).fetchall()

        run = WorkflowRun(
            workflow_name=row["workflow_name"],
            run_id=row["run_id"],
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            initial_context=json.loads(row["initial_context"] or "{}"),
            final_context=json.loads(row["final_context"] or "{}"),
            error=row["error"],
        )
        for nr in node_rows:
            node_run = NodeRun(
                node_id=nr["node_id"],
                run_id=run_id,
                status=NodeStatus(nr["status"]),
                started_at=datetime.fromisoformat(nr["started_at"]) if nr["started_at"] else None,
                completed_at=datetime.fromisoformat(nr["completed_at"]) if nr["completed_at"] else None,
                output=json.loads(nr["output"] or "{}"),
                error=nr["error"],
                attempt=nr["attempt"],
            )
            run.node_runs[node_run.node_id] = node_run
        return run

    # ------------------------------------------------------------------
    # NodeRun CRUD
    # ------------------------------------------------------------------

    def upsert_node_run(self, node_run: NodeRun) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO node_runs
                   (id, run_id, node_id, status, started_at, completed_at, output, error, attempt)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    f"{node_run.run_id}:{node_run.node_id}",
                    node_run.run_id,
                    node_run.node_id,
                    node_run.status.value,
                    node_run.started_at.isoformat() if node_run.started_at else None,
                    node_run.completed_at.isoformat() if node_run.completed_at else None,
                    json.dumps(self._safe_json(node_run.output)),
                    node_run.error,
                    node_run.attempt,
                ),
            )

    def list_runs(self, workflow_name: str | None = None, limit: int = 50) -> list[WorkflowRun]:
        with self._conn() as conn:
            if workflow_name:
                rows = conn.execute(
                    "SELECT * FROM workflow_runs WHERE workflow_name=? ORDER BY started_at DESC LIMIT ?",
                    (workflow_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            WorkflowRun(
                workflow_name=r["workflow_name"],
                run_id=r["run_id"],
                status=RunStatus(r["status"]),
                started_at=datetime.fromisoformat(r["started_at"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_json(obj: Any) -> Any:
        """Strip non-serialisable values (e.g., dataclass instances)."""
        if isinstance(obj, dict):
            return {k: WorkflowStateStore._safe_json(v) for k, v in obj.items()
                    if isinstance(k, str) and not k.startswith("_")}
        if isinstance(obj, (list, tuple)):
            return [WorkflowStateStore._safe_json(i) for i in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)
