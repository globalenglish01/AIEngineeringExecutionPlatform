"""BaseAgent — core agent loop with tool use and memory."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from aeep.agents.models import AgentResult, AgentStatus, AgentStep
from aeep.agents.tool_registry import ToolRegistry
from aeep.core.models.message import Message, Role

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider
    from aeep.memory.memory_store import MemoryStore


class BaseAgent:
    """ReAct-style agent with pluggable tools and memory."""

    def __init__(
        self,
        name: str,
        role: str,
        provider: LLMProvider,
        tools: list[Any] | None = None,
        memory: MemoryStore | None = None,
        max_iterations: int = 10,
        model: str = "gpt-4o-mini",
    ) -> None:
        self.name = name
        self.role = role
        self._provider = provider
        self._model = model
        self._max_iterations = max_iterations
        self._memory = memory
        self._registry = ToolRegistry()
        for tool in (tools or []):
            self._registry.register(tool)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        from aeep.agents.reasoning.react import ReActLoop
        loop = ReActLoop(agent=self)
        return await loop.run(task, context or {})

    async def step(self, messages: list[Message]) -> AgentStep:
        """Single LLM inference step; returns parsed thought/action."""
        tool_schemas = self._registry.openai_schemas()
        result = await self._provider.complete(
            messages=messages,
            model=self._model,
            temperature=0.2,
            max_tokens=1024,
        )
        return self._parse_step(result.content)

    async def use_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return its string output."""
        try:
            result = await self._registry.execute(tool_name, args)
            return str(result)
        except KeyError:
            return f"Error: tool {tool_name!r} not found"
        except Exception as e:
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_step(self, content: str) -> AgentStep:
        """Parse LLM response into thought/action/finish."""
        step = AgentStep()
        lines = content.strip().splitlines()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Thought:"):
                step.thought = stripped[len("Thought:"):].strip()
            elif stripped.startswith("Action:"):
                step.action = stripped[len("Action:"):].strip()
            elif stripped.startswith("Action Input:"):
                raw = stripped[len("Action Input:"):].strip()
                try:
                    step.action_input = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    step.action_input = {"input": raw}
            elif stripped.startswith("Final Answer:"):
                step.thought = stripped[len("Final Answer:"):].strip()
                step.is_final = True

        if not step.action and not step.is_final:
            # Treat entire response as final answer if no structure
            step.thought = content.strip()
            step.is_final = True

        return step

    def _system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in [self._registry.get(n) for n in self._registry.list_names()]
        )
        return (
            f"You are {self.name}, {self.role}\n\n"
            "Use the ReAct format:\n"
            "Thought: <your reasoning>\n"
            "Action: <tool_name or 'finish'>\n"
            "Action Input: <JSON args>\n"
            "...repeat until done, then:\n"
            "Final Answer: <your final response>\n\n"
            f"Available tools:\n{tool_descriptions or '(none)'}"
        )

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def memory(self) -> MemoryStore | None:
        return self._memory