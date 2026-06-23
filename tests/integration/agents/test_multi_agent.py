"""Integration tests for Supervisor + Worker multi-agent pattern."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from aeep.agents.models import AgentStatus
from aeep.agents.multi_agent import SupervisorAgent, WorkerAgent
from aeep.core.models.message import CompletionResult


def _mock_provider() -> MagicMock:
    mock = MagicMock()
    mock.complete = AsyncMock(
        return_value=CompletionResult(
            content="Final Answer: Sub-task completed successfully.",
            model="gpt-4o-mini",
            provider_name="mock",
            input_tokens=10,
            output_tokens=20,
            finish_reason="stop",
            duration_ms=1,
        )
    )
    return mock


class TestSupervisorAgent:
    @pytest.mark.asyncio
    async def test_parallel_workers_complete(self):
        workers = [
            WorkerAgent("worker1", "worker", _mock_provider(), max_iterations=3),
            WorkerAgent("worker2", "worker", _mock_provider(), max_iterations=3),
        ]
        supervisor = SupervisorAgent(
            name="supervisor",
            workers=workers,
            provider=_mock_provider(),
        )
        result = await supervisor.run(
            task="Build a feature",
            subtasks=["Write tests", "Write implementation"],
        )
        assert result.status == AgentStatus.COMPLETED
        assert len(result.sub_results) == 2
        assert all(r.status == AgentStatus.COMPLETED for r in result.sub_results.values())

    @pytest.mark.asyncio
    async def test_summary_contains_task(self):
        workers = [WorkerAgent("w1", "worker", _mock_provider(), max_iterations=3)]
        supervisor = SupervisorAgent("sup", workers=workers, provider=_mock_provider())
        result = await supervisor.run("Main goal", subtasks=["Do the thing"])
        assert "Main goal" in result.final_summary

    @pytest.mark.asyncio
    async def test_no_workers_fails(self):
        supervisor = SupervisorAgent("sup", workers=[], provider=_mock_provider())
        result = await supervisor.run("task", subtasks=["work"])
        assert result.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_no_subtasks_fails(self):
        workers = [WorkerAgent("w1", "worker", _mock_provider(), max_iterations=3)]
        supervisor = SupervisorAgent("sup", workers=workers, provider=_mock_provider())
        result = await supervisor.run("task", subtasks=[])
        assert result.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_three_workers_four_subtasks(self):
        """More subtasks than workers — round-robin assignment."""
        workers = [WorkerAgent(f"w{i}", "worker", _mock_provider(), max_iterations=3) for i in range(3)]
        supervisor = SupervisorAgent("sup", workers=workers, provider=_mock_provider())
        subtasks = [f"task {i}" for i in range(4)]
        result = await supervisor.run("big job", subtasks=subtasks)
        assert result.status == AgentStatus.COMPLETED
        assert len(result.sub_results) == 4
