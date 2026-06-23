"""Agent interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from aeep.core.models.message import Message


class AgentState:
    __slots__ = ("thoughts", "observations", "iteration", "metadata")

    def __init__(self) -> None:
        self.thoughts: list[str] = []
        self.observations: list[str] = []
        self.iteration: int = 0
        self.metadata: dict[str, Any] = {}


@runtime_checkable
class Agent(Protocol):
    name: str
    max_iterations: int

    async def run(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Execute the agent's ReAct loop and return the final answer."""
        ...

    async def step(self, state: AgentState, messages: list[Message]) -> AgentState:
        """Single thought→action→observation cycle."""
        ...
