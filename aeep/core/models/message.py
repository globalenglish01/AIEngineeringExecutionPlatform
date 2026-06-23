"""Core message and LLM completion models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: Role
    content: str
    name: str | None = None  # speaker name in multi-agent scenarios

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class CompletionResult:
    content: str
    model: str
    provider_name: str
    input_tokens: int
    output_tokens: int
    finish_reason: str  # "stop" | "length" | "tool_calls"
    duration_ms: int
    raw_response: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class StreamChunk:
    delta: str
    is_final: bool
    finish_reason: str | None = None
