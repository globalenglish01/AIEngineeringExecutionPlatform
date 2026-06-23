"""Multi-Agent Supervisor/Worker pattern."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from aeep.agents.base_agent import BaseAgent
from aeep.agents.models import AgentResult, AgentStatus

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider


@dataclass
class SubTask:
    task_id: str
    description: str
    assigned_to: str = ""
    result: AgentResult | None = None
    attempts: int = 0


@dataclass
class SupervisorResult:
    status: AgentStatus
    sub_results: dict[str, AgentResult] = field(default_factory=dict)
    final_summary: str = ""
    error: str = ""


class WorkerAgent(BaseAgent):
    """A worker that executes assigned sub-tasks."""


class SupervisorAgent:
    """Decomposes a task, assigns to workers, aggregates results.

    Workers run in parallel; failed tasks are reassigned to the next
    available worker (round-robin) up to ``max_retries`` times.
    """

    def __init__(
        self,
        name: str,
        workers: list[WorkerAgent],
        provider: LLMProvider,
        model: str = "gpt-4o-mini",
        max_retries: int = 2,
    ) -> None:
        self.name = name
        self._workers = workers
        self._provider = provider
        self._model = model
        self._max_retries = max_retries

    async def run(self, task: str, subtasks: list[str]) -> SupervisorResult:
        """Run subtasks in parallel across workers.

        Args:
            task: The high-level goal (used for final summary).
            subtasks: Pre-defined list of sub-task descriptions.
        """
        if not subtasks:
            return SupervisorResult(
                status=AgentStatus.FAILED,
                error="No subtasks provided",
            )
        if not self._workers:
            return SupervisorResult(
                status=AgentStatus.FAILED,
                error="No workers available",
            )

        pending: list[SubTask] = [
            SubTask(task_id=f"t{i}", description=desc)
            for i, desc in enumerate(subtasks)
        ]

        results: dict[str, AgentResult] = {}
        attempts: dict[str, int] = {st.task_id: 0 for st in pending}

        while pending:
            # Assign round-robin
            assignments: list[tuple[SubTask, WorkerAgent]] = []
            for i, st in enumerate(pending):
                worker = self._workers[i % len(self._workers)]
                st.assigned_to = worker.name
                assignments.append((st, worker))

            # Run all in parallel
            async def _run_one(subtask: SubTask, worker: WorkerAgent) -> tuple[str, AgentResult]:
                result = await worker.run(subtask.description, {})
                return subtask.task_id, result

            outcomes = await asyncio.gather(
                *[_run_one(st, w) for st, w in assignments],
                return_exceptions=True,
            )

            still_pending: list[SubTask] = []
            for i, (st, _) in enumerate(assignments):
                outcome = outcomes[i]
                attempts[st.task_id] += 1
                if isinstance(outcome, Exception):
                    result = AgentResult(status=AgentStatus.FAILED, error=str(outcome))
                else:
                    _, result = outcome  # type: ignore[misc]

                if result.status == AgentStatus.COMPLETED:
                    results[st.task_id] = result
                elif attempts[st.task_id] < self._max_retries:
                    still_pending.append(st)
                else:
                    # Give up
                    results[st.task_id] = result

            pending = still_pending

        all_ok = all(r.status == AgentStatus.COMPLETED for r in results.values())
        summary = self._aggregate(task, results)

        return SupervisorResult(
            status=AgentStatus.COMPLETED if all_ok else AgentStatus.FAILED,
            sub_results=results,
            final_summary=summary,
        )

    @staticmethod
    def _aggregate(task: str, results: dict[str, AgentResult]) -> str:
        lines = [f"Supervisor summary for: {task}", ""]
        for tid, r in sorted(results.items()):
            status = "OK" if r.status == AgentStatus.COMPLETED else "FAILED"
            lines.append(f"[{tid}] {status}: {r.output[:200]}")
        return "\n".join(lines)