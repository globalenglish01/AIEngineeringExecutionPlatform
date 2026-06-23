"""Unified memory interface combining short-term and long-term memory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from aeep.memory.long_term import LongTermMemory, MemoryEntry
from aeep.memory.short_term import ShortTermMemory

if TYPE_CHECKING:
    from aeep.core.models.message import Message


# Re-export MemoryEntry as Memory for the public API
Memory = MemoryEntry


@dataclass
class MemoryStore:
    """Unified store combining short-term and long-term memory."""

    max_short_term: int = 50
    collection_name: str = "aeep_memory"
    persist_directory: str | Path | None = None

    def __post_init__(self) -> None:
        self.short_term = ShortTermMemory(max_messages=self.max_short_term)
        self.long_term = LongTermMemory(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
        )

    # ------------------------------------------------------------------
    # Short-term delegation
    # ------------------------------------------------------------------

    def add_message(self, message: Message) -> None:
        self.short_term.add(message)

    def get_messages(self) -> list[Message]:
        return self.short_term.get_messages()

    # ------------------------------------------------------------------
    # Long-term delegation
    # ------------------------------------------------------------------

    def save(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        return self.long_term.save(content, metadata)

    def search(self, query: str, k: int = 5) -> list[Memory]:
        return self.long_term.search(query, k)

    def forget(self, memory_id: str) -> None:
        self.long_term.forget(memory_id)

    # ------------------------------------------------------------------
    # Composite helpers
    # ------------------------------------------------------------------

    def get_context_for_task(self, task: str) -> str:
        """Return a context string with relevant long-term memories + recent messages."""
        memories = self.long_term.search(task, k=5)
        parts: list[str] = []

        if memories:
            parts.append("=== Relevant memories ===")
            for m in memories:
                parts.append(f"- {m.content}")

        history = self.short_term.to_context_string()
        if history:
            parts.append("=== Recent conversation ===")
            parts.append(history)

        return "\n".join(parts)
