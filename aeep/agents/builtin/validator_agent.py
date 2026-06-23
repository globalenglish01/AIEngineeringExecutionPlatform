"""Validator agent — quality review, scoring, and issue identification."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from aeep.agents.base_agent import BaseAgent
from aeep.agents.tools.file_tool import FileTool
from aeep.agents.tools.shell_tool import ShellTool
from aeep.agents.tools.validation_tool import ValidationTool

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider
    from aeep.memory.memory_store import MemoryStore


class ValidatorAgent(BaseAgent):
    """Specializes in code review, content scoring, and issue identification."""

    def __init__(
        self,
        provider: LLMProvider,
        memory: MemoryStore | None = None,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="ValidatorAgent",
            role="a rigorous quality validator who reviews outputs for correctness and completeness",
            provider=provider,
            tools=[ValidationTool(), ShellTool(), FileTool()],
            memory=memory,
            model=model,
            **kwargs,
        )