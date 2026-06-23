"""Agent-specific data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentStep:
    """Result of a single ReAct step."""
    thought: str = ""
    action: str = ""          # tool name or "finish"
    action_input: dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    is_final: bool = False


@dataclass
class AgentResult:
    status: AgentStatus
    output: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    error: str = ""
    iterations: int = 0