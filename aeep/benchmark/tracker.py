"""Benchmark tracker — persists results, detects regressions, emits trend data."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aeep.benchmark.runner import BenchmarkReport


@dataclass
class RegressionAlert:
    suite_id: str
    run_id: str
    baseline_run_id: str
    score_delta: float
    task_regressions: list[dict[str, Any]] = field(default_factory=list)


class BenchmarkTracker:
    """SQLite-backed storage for benchmark run history."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                run_id      TEXT PRIMARY KEY,
                suite_id    TEXT NOT NULL,
                suite_name  TEXT NOT NULL,
                mean_score  REAL NOT NULL,
                pass_rate   REAL NOT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                report_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_suite ON benchmark_runs(suite_id, started_at);
        """)
        self._conn.commit()

    def save(self, report: BenchmarkReport) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO benchmark_runs VALUES (?,?,?,?,?,?,?,?)",
            (
                report.run_id,
                report.suite_id,
                report.suite_name,
                report.mean_score,
                report.pass_rate,
                report.started_at,
                report.finished_at,
                json.dumps(report.to_json()),
            ),
        )
        self._conn.commit()

    def get_latest(self, suite_id: str, n: int = 1) -> list[BenchmarkReport]:
        rows = self._conn.execute(
            "SELECT report_json FROM benchmark_runs WHERE suite_id=? "
            "ORDER BY started_at DESC LIMIT ?",
            (suite_id, n),
        ).fetchall()
        return [self._deserialize(r[0]) for r in rows]

    def get_run(self, run_id: str) -> BenchmarkReport | None:
        row = self._conn.execute(
            "SELECT report_json FROM benchmark_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return self._deserialize(row[0]) if row else None

    def check_regression(
        self,
        report: BenchmarkReport,
        threshold: float = 5.0,
    ) -> RegressionAlert | None:
        """Compare report against most recent baseline; return alert if regression detected."""
        previous = self.get_latest(report.suite_id, n=1)
        if not previous:
            return None
        baseline = previous[0]
        delta = report.mean_score - baseline.mean_score
        if delta < -threshold:
            # Find per-task regressions
            baseline_scores = {r.task_id: r.score for r in baseline.task_results}
            regressions = [
                {
                    "task_id": r.task_id,
                    "current": r.score,
                    "baseline": baseline_scores.get(r.task_id, 0.0),
                    "delta": r.score - baseline_scores.get(r.task_id, 0.0),
                }
                for r in report.task_results
                if r.score < baseline_scores.get(r.task_id, 0.0) - threshold
            ]
            return RegressionAlert(
                suite_id=report.suite_id,
                run_id=report.run_id,
                baseline_run_id=baseline.run_id,
                score_delta=round(delta, 2),
                task_regressions=regressions,
            )
        return None

    def trend_data(self, suite_id: str, last_n: int = 10) -> list[dict[str, Any]]:
        """Return time-series data for plotting."""
        rows = self._conn.execute(
            "SELECT run_id, mean_score, pass_rate, started_at FROM benchmark_runs "
            "WHERE suite_id=? ORDER BY started_at ASC LIMIT ?",
            (suite_id, last_n),
        ).fetchall()
        return [
            {"run_id": r[0], "mean_score": r[1], "pass_rate": r[2], "started_at": r[3]}
            for r in rows
        ]

    @staticmethod
    def _deserialize(report_json: str) -> BenchmarkReport:
        from aeep.benchmark.runner import TaskResult
        data = json.loads(report_json)
        return BenchmarkReport(
            suite_id=data["suite_id"],
            suite_name=data["suite_name"],
            run_id=data["run_id"],
            started_at=data["started_at"],
            finished_at=data["finished_at"],
            task_results=[
                TaskResult(
                    task_id=r["task_id"],
                    task_name=r["task_name"],
                    score=r["score"],
                    passed=r["passed"],
                    duration_ms=r["duration_ms"],
                    error=r.get("error", ""),
                )
                for r in data.get("task_results", [])
            ],
            metadata=data.get("metadata", {}),
        )
