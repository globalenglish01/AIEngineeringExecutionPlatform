"""Writer agent — documentation, chapter creation, content optimization."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from aeep.agents.base_agent import BaseAgent
from aeep.agents.tools.file_tool import FileTool
from aeep.agents.tools.web_tool import WebTool
from aeep.agents.tools.validation_tool import ValidationTool

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider
    from aeep.memory.memory_store import MemoryStore


class WriterAgent(BaseAgent):
    """Specializes in technical writing, documentation, and content creation."""

    def __init__(
        self,
        provider: LLMProvider,
        memory: MemoryStore | None = None,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="WriterAgent",
            role="a technical writing expert who creates clear, engaging documentation and content",
            provider=provider,
            tools=[FileTool(), WebTool(), ValidationTool()],
            memory=memory,
            model=model,
            **kwargs,
        )