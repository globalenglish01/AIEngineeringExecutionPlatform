"""Tests for the ReAct reasoning loop."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from aeep.agents.base_agent import BaseAgent
from aeep.agents.models import AgentStatus
from aeep.agents.reasoning.react import ReActLoop
from aeep.agents.tools.base_tool import BaseTool, ToolResult
from aeep.core.models.message import CompletionResult, Role


def _provider_sequence(responses: list[str]) -> MagicMock:
    """Provider that returns responses in sequence."""
    mock = MagicMock()
    results = [
        CompletionResult(content=r, model="gpt-4o-mini", provider_name="mock", input_tokens=5, output_tokens=10, finish_reason="stop", duration_ms=1)
        for r in responses
    ]
    mock.complete = AsyncMock(side_effect=results)
    return mock


class _CounterTool(BaseTool):
    name = "counter"
    description = "Returns the call count"
    input_schema = {"type": "object", "properties": {}}
    _calls = 0

    async def execute(self, args: dict) -> ToolResult:
        _CounterTool._calls += 1
        return ToolResult(success=True, output=f"call #{_CounterTool._calls}")


class TestReActLoop:
    @pytest.mark.asyncio
    async def test_immediate_final_answer(self):
        provider = _provider_sequence(["Final Answer: Task complete."])
        agent = BaseAgent("A", "tester", provider, max_iterations=5)
        result = await agent.run("do something")
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "Task complete."
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_tool_then_final(self):
        _CounterTool._calls = 0
        responses = [
            'Thought: I will count\nAction: counter\nAction Input: {}',
            "Final Answer: Counted once.",
        ]
        provider = _provider_sequence(responses)
        agent = BaseAgent("A", "tester", provider, tools=[_CounterTool()], max_iterations=5)
        result = await agent.run("count something")
        assert result.status == AgentStatus.COMPLETED
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_max_iterations_exceeded(self):
        # Agent never gives a final answer
        provider = _provider_sequence(
            ['Thought: thinking\nAction: counter\nAction Input: {}'] * 20
        )
        agent = BaseAgent("A", "tester", provider, tools=[_CounterTool()], max_iterations=3)
        result = await agent.run("infinite loop")
        assert result.status == AgentStatus.FAILED
        assert "max_iterations" in result.error

    @pytest.mark.asyncio
    async def test_steps_recorded(self):
        responses = [
            'Thought: step1\nAction: counter\nAction Input: {}',
            "Final Answer: Done.",
        ]
        provider = _provider_sequence(responses)
        agent = BaseAgent("A", "tester", provider, tools=[_CounterTool()], max_iterations=5)
        result = await agent.run("task")
        assert len(result.steps) == 2
        assert result.steps[0].thought == "step1"
        assert result.steps[1].is_final
