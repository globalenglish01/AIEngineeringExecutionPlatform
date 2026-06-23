"""Workflow and WorkflowNode interfaces."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@runtime_checkable
class WorkflowNode(Protocol):
    node_id: str
    node_type: str   # "llm" | "validation" | "tool" | "parallel" | "loop" | "condition"
    depends_on: list[str]  # node_ids that must complete before this runs

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run this node and return updated context."""
        ...


@runtime_checkable
class Workflow(Protocol):
    workflow_id: str
    name: str
    nodes: list[WorkflowNode]

    async def run(self, initial_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the full workflow DAG and return the final context."""
        ...

    async def resume(self, checkpoint_id: str) -> dict[str, Any]:
        """Resume from a saved checkpoint."""
        ...
