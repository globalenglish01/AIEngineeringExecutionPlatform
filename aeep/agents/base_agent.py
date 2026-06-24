"""BaseAgent — core agent loop with tool use and memory."""

from __future__ import annotations

import json
import re
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

    # Both English and Chinese keyword variants are accepted
    _THOUGHT_KW  = ("Thought:", "思考：", "思考:")
    _ACTION_KW   = ("Action:", "行动：", "行动:")
    _INPUT_KW    = ("Action Input:", "输入：", "输入:")
    _FINAL_KW    = ("Final Answer:", "最终答案：", "最终答案:")

    def _parse_step(self, content: str) -> AgentStep:
        """Parse LLM response into thought/action/finish.

        Supports both English (Thought/Action/Action Input/Final Answer)
        and Chinese (思考/行动/输入/最终答案) keyword variants.
        """
        step = AgentStep()
        # Normalise "思考\n：xxx" → "思考：xxx" (colon split across lines)
        content = re.sub(r'(思考|行动|输入|最终答案)\s*\n\s*[：:]', r'\1：', content)
        lines = content.strip().splitlines()
        # Collect multi-line Action Input / 输入 blocks
        input_lines: list[str] = []
        collecting_input = False

        for line in lines:
            stripped = line.strip()

            if any(stripped.startswith(kw) for kw in self._FINAL_KW):
                kw = next(kw for kw in self._FINAL_KW if stripped.startswith(kw))
                step.thought = stripped[len(kw):].strip()
                step.is_final = True
                collecting_input = False
            elif any(stripped.startswith(kw) for kw in self._THOUGHT_KW):
                kw = next(kw for kw in self._THOUGHT_KW if stripped.startswith(kw))
                step.thought = stripped[len(kw):].strip()
                collecting_input = False
            elif any(stripped.startswith(kw) for kw in self._ACTION_KW):
                kw = next(kw for kw in self._ACTION_KW if stripped.startswith(kw))
                step.action = stripped[len(kw):].strip()
                collecting_input = False
            elif any(stripped.startswith(kw) for kw in self._INPUT_KW):
                kw = next(kw for kw in self._INPUT_KW if stripped.startswith(kw))
                input_lines = [stripped[len(kw):].strip()]
                collecting_input = True
            elif collecting_input:
                input_lines.append(line)

        if input_lines:
            raw = "\n".join(input_lines).strip()
            try:
                step.action_input = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                # Fix unescaped Windows backslashes (e.g. C:\Users → C:\\Users)
                fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
                try:
                    step.action_input = json.loads(fixed)
                except (json.JSONDecodeError, ValueError):
                    step.action_input = {"input": raw}

        if not step.action and not step.is_final:
            # No structure found — treat entire response as final answer
            step.thought = content.strip()
            step.is_final = True

        return step

    def _system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in [self._registry.get(n) for n in self._registry.list_names()]
        )
        return (
            f"你是{self.role}\n\n"
            "【输出格式】每次只输出以下一个步骤，等待工具结果后再继续：\n"
            "思考：<分析>\n"
            "行动：<工具名>\n"
            "输入：<合法JSON，Windows路径用双反斜杠 C:\\\\Users\\\\xxx>\n\n"
            "所有步骤完成后输出：\n"
            "最终答案：<结果>\n\n"
            f"【可用工具】\n{tool_descriptions or '（无工具）'}\n"
            "file_tool read_csv参数：path、columns（数组）、limit（整数）、offset（整数）"
        )

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def memory(self) -> MemoryStore | None:
        return self._memory