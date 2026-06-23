"""Memory tool — save and search memories via MemoryStore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult

if TYPE_CHECKING:
    from aeep.memory.memory_store import MemoryStore


class MemoryTool(BaseTool):
    name = "memory_tool"
    description = "Save important information to long-term memory or search existing memories."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save_memory", "search_memory"],
                "description": "save_memory: persist content. search_memory: retrieve related memories.",
            },
            "content": {"type": "string", "description": "Content to save (save_memory only)."},
            "query": {"type": "string", "description": "Search query (search_memory only)."},
            "k": {"type": "integer", "description": "Number of memories to retrieve (default 5)."},
        },
        "required": ["action"],
    }

    def __init__(self, memory_store: MemoryStore) -> None:
        self._store = memory_store

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")

        if action == "save_memory":
            content = args.get("content", "")
            if not content:
                return ToolResult(success=False, error="content is required for save_memory")
            memory_id = self._store.save(content)
            return ToolResult(success=True, output=f"Saved memory: {memory_id}")

        elif action == "search_memory":
            query = args.get("query", "")
            k = int(args.get("k", 5))
            if not query:
                return ToolResult(success=False, error="query is required for search_memory")
            results = self._store.search(query, k=k)
            output = [{"id": m.memory_id, "content": m.content} for m in results]
            return ToolResult(success=True, output=output)

        else:
            return ToolResult(success=False, error=f"Unknown action: {action!r}")