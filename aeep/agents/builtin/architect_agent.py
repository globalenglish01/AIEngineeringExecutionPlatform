"""Architect agent — requirements analysis and system design."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from aeep.agents.base_agent import BaseAgent
from aeep.agents.tools.file_tool import FileTool
from aeep.agents.tools.search_tool import SearchTool
from aeep.agents.tools.web_tool import WebTool

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider
    from aeep.memory.memory_store import MemoryStore


class ArchitectAgent(BaseAgent):
    """Specializes in requirements analysis, architecture design, and tech selection."""

    def __init__(
        self,
        provider: LLMProvider,
        memory: MemoryStore | None = None,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="ArchitectAgent",
            role="an expert software architect specializing in system design and technology selection",
            provider=provider,
            tools=[SearchTool(), WebTool(), FileTool()],
            memory=memory,
            model=model,
            **kwargs,
        )