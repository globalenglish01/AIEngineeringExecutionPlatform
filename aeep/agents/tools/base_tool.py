"""Base Tool interface — all tools implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: str = ""

    def __str__(self) -> str:
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolResult:
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Emit OpenAI Function Calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }