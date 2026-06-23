"""Engineer agent — code generation, refactoring, testing."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from aeep.agents.base_agent import BaseAgent
from aeep.agents.tools.file_tool import FileTool
from aeep.agents.tools.shell_tool import ShellTool
from aeep.agents.tools.validation_tool import ValidationTool

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider
    from aeep.memory.memory_store import MemoryStore


class EngineerAgent(BaseAgent):
    """Specializes in code generation, refactoring, and test writing."""

    def __init__(
        self,
        provider: LLMProvider,
        memory: MemoryStore | None = None,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="EngineerAgent",
            role="a senior software engineer who writes clean, well-tested production code",
            provider=provider,
            tools=[FileTool(), ShellTool(), ValidationTool()],
            memory=memory,
            model=model,
            **kwargs,
        )