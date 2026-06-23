"""Tests for BaseAgent parsing and tool execution."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from aeep.agents.base_agent import BaseAgent
from aeep.agents.models import AgentStep
from aeep.agents.tools.base_tool import BaseTool, ToolResult
from aeep.agents.tool_registry import ToolRegistry
from aeep.core.models.message import CompletionResult, Message, Role


def _make_provider(response: str) -> MagicMock:
    """Create a mock LLMProvider that returns a fixed response."""
    mock = MagicMock()
    cr = CompletionResult(
        content=response,
        model="gpt-4o-mini",
        provider_name="mock",
        input_tokens=10,
        output_tokens=20,
        finish_reason="stop",
        duration_ms=1,
    )
    mock.complete = AsyncMock(return_value=cr)
    return mock


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes its input"
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, args: dict) -> ToolResult:
        return ToolResult(success=True, output=args.get("text", ""))


class TestBaseAgentParsing:
    def test_parse_final_answer(self):
        provider = _make_provider("irrelevant")
        agent = BaseAgent("TestAgent", "tester", provider)
        step = agent._parse_step("Final Answer: All done!")
        assert step.is_final
        assert step.thought == "All done!"

    def test_parse_thought_action(self):
        provider = _make_provider("irrelevant")
        agent = BaseAgent("TestAgent", "tester", provider)
        raw = 'Thought: I should echo\nAction: echo\nAction Input: {"text": "hello"}'
        step = agent._parse_step(raw)
        assert not step.is_final
        assert step.thought == "I should echo"
        assert step.action == "echo"
        assert step.action_input == {"text": "hello"}

    def test_parse_unstructured_as_final(self):
        provider = _make_provider("")
        agent = BaseAgent("TestAgent", "tester", provider)
        step = agent._parse_step("Just a plain response with no structure")
        assert step.is_final

    @pytest.mark.asyncio
    async def test_use_tool_success(self):
        provider = _make_provider("")
        agent = BaseAgent("TestAgent", "tester", provider, tools=[_EchoTool()])
        result = await agent.use_tool("echo", {"text": "ping"})
        assert "ping" in result

    @pytest.mark.asyncio
    async def test_use_unknown_tool(self):
        provider = _make_provider("")
        agent = BaseAgent("TestAgent", "tester", provider)
        result = await agent.use_tool("nonexistent", {})
        assert "Error" in result

    def test_system_prompt_contains_role(self):
        provider = _make_provider("")
        agent = BaseAgent("MyAgent", "a helpful assistant", provider)
        prompt = agent._system_prompt()
        assert "MyAgent" in prompt
        assert "helpful assistant" in prompt


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        tool = reg.get("echo")
        assert tool.name == "echo"

    def test_get_nonexistent_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.get("missing")

    def test_openai_schemas(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        schemas = reg.openai_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_execute_via_registry(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        result = await reg.execute("echo", {"text": "world"})
        assert result.success
        assert result.output == "world"
