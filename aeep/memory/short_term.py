"""Short-term (in-session) conversation memory with sliding-window trimming."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aeep.core.models.message import Message


@dataclass
class ShortTermMemory:
    """Stores the current session's conversation history.

    Automatically trims old messages when the window exceeds `max_messages`.
    Optionally keeps a summary of trimmed history.
    """

    max_messages: int = 50
    _messages: list[Message] = field(default_factory=list, init=False, repr=False)
    _summary: str = field(default="", init=False, repr=False)

    def add(self, message: Message) -> None:
        self._messages.append(message)
        if len(self._messages) > self.max_messages:
            self._trim()

    def _trim(self) -> None:
        keep = self.max_messages // 2
        dropped = self._messages[: len(self._messages) - keep]
        self._messages = self._messages[-keep:]
        # Simple summary: concatenate role+first-50-chars of dropped messages
        fragments = [f"[{m.role}]: {str(m.content)[:50]}" for m in dropped]
        new_summary = "; ".join(fragments)
        if self._summary:
            self._summary = f"{self._summary} | {new_summary}"
        else:
            self._summary = new_summary

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def get_summary(self) -> str:
        return self._summary

    def clear(self) -> None:
        self._messages = []
        self._summary = ""

    def __len__(self) -> int:
        return len(self._messages)

    def to_context_string(self) -> str:
        parts: list[str] = []
        if self._summary:
            parts.append(f"[Earlier conversation summary]: {self._summary}")
        for m in self._messages:
            parts.append(f"{m.role}: {m.content}")
        return "\n".join(parts)
