"""Tool registry — register, discover, and generate schemas for tools."""

from __future__ import annotations

from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for all available agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name!r}")
        return self._tools[name]

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def openai_schemas(self) -> list[dict[str, Any]]:
        """Return all tool schemas in OpenAI Function Calling format."""
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        return await tool.execute(args)