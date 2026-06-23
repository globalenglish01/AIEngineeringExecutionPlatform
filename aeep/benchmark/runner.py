"""Benchmark runner — executes suites, scores results, produces reports."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from aeep.benchmark.suite import BenchmarkSuite, BenchmarkTask


@dataclass
class TaskResult:
    task_id: str
    task_name: str
    score: float
    passed: bool
    duration_ms: int
    output: str = ""
    issues: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class BenchmarkReport:
    suite_id: str
    suite_name: str
    run_id: str
    started_at: str
    finished_at: str
    task_results: list[TaskResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean_score(self) -> float:
        scores = [r.score for r in self.task_results if not r.error]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def pass_rate(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(1 for r in self.task_results if r.passed) / len(self.task_results)

    def to_json(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "mean_score": round(self.mean_score, 2),
            "pass_rate": round(self.pass_rate, 3),
            "task_results": [
                {
                    "task_id": r.task_id,
                    "task_name": r.task_name,
                    "score": r.score,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in self.task_results
            ],
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Benchmark Report: {self.suite_name}",
            f"",
            f"**Run**: `{self.run_id}`  ",
            f"**Mean Score**: {self.mean_score:.1f}/100  ",
            f"**Pass Rate**: {self.pass_rate * 100:.0f}%  ",
            f"**Tasks**: {len(self.task_results)}",
            f"",
            "## Task Results",
            "",
            "| Task | Score | Passed | Duration |",
            "| --- | --- | --- | --- |",
        ]
        for r in self.task_results:
            status = "✅" if r.passed else "❌"
            lines.append(f"| {r.task_name} | {r.score:.1f} | {status} | {r.duration_ms}ms |")
        return "\n".join(lines)


class BenchmarkRunner:
    """Executes a BenchmarkSuite, scoring each task via a provided scorer."""

    def __init__(
        self,
        scorer: Callable[[BenchmarkTask, str], Any] | None = None,
    ) -> None:
        # scorer(task, generated_output) → score (float) or TaskResult
        self._scorer = scorer or self._default_scorer

    async def run(
        self,
        suite: BenchmarkSuite,
        generator: Callable[[str], Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkReport:
        """Run all tasks in the suite.

        Args:
            suite: The benchmark suite to run.
            generator: async callable(input_text) → output_text. Uses the task
                       description as output if None.
            metadata: Optional extra info to attach to the report.
        """
        import uuid
        run_id = uuid.uuid4().hex[:8]
        started_at = datetime.now(UTC).isoformat()
        task_results: list[TaskResult] = []

        for task in suite.tasks:
            t0 = time.monotonic()
            try:
                if generator is not None:
                    if asyncio.iscoroutinefunction(generator):
                        output = await generator(task.input)
                    else:
                        output = generator(task.input)
                else:
                    output = task.description  # use description as placeholder output

                score, issues = self._score(task, str(output))
                passed = score >= task.min_score
            except Exception as e:
                output = ""
                score = 0.0
                issues = []
                passed = False
                task_results.append(
                    TaskResult(
                        task_id=task.task_id,
                        task_name=task.name,
                        score=0.0,
                        passed=False,
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        error=str(e),
                    )
                )
                continue

            task_results.append(
                TaskResult(
                    task_id=task.task_id,
                    task_name=task.name,
                    score=round(score, 1),
                    passed=passed,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    output=str(output)[:500],
                    issues=issues,
                )
            )

        return BenchmarkReport(
            suite_id=suite.suite_id,
            suite_name=suite.name,
            run_id=run_id,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            task_results=task_results,
            metadata=metadata or {},
        )

    def _score(self, task: BenchmarkTask, output: str) -> tuple[float, list[str]]:
        return self._scorer(task, output)

    @staticmethod
    def _default_scorer(task: BenchmarkTask, output: str) -> tuple[float, list[str]]:
        """Heuristic scorer: keyword presence + word count."""
        words = output.split()
        word_score = min(50.0, len(words) / 10.0)

        keyword_hits = sum(
            1 for kw in task.expected_keywords if kw.lower() in output.lower()
        )
        keyword_score = (
            50.0 * keyword_hits / len(task.expected_keywords)
            if task.expected_keywords
            else 50.0
        )

        score = word_score + keyword_score
        issues: list[str] = []
        missing = [kw for kw in task.expected_keywords if kw.lower() not in output.lower()]
        if missing:
            issues.append(f"Missing keywords: {', '.join(missing)}")
        return min(100.0, score), issues
