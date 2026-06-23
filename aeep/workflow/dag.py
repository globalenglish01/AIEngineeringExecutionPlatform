"""DAG — Directed Acyclic Graph execution engine.

Supports:
- Topological sort with cycle detection
- Parallel execution of independent nodes (asyncio.gather)
- Data-flow: each node's output is merged into the shared context
- Resume from checkpoint (skip COMPLETED nodes)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any

from aeep.core.interfaces.workflow import NodeStatus

logger = logging.getLogger(__name__)


class CycleDetectedError(Exception):
    pass


class DAGNode:
    """Lightweight wrapper that a node must expose for DAG scheduling."""

    def __init__(
        self,
        node_id: str,
        node_type: str,
        depends_on: list[str] | None = None,
    ) -> None:
        self.node_id = node_id
        self.node_type = node_type
        self.depends_on: list[str] = depends_on or []


class DAG:
    """Directed Acyclic Graph with topological ordering and parallel execution."""

    def __init__(self) -> None:
        self._nodes: dict[str, Any] = {}   # node_id → node object (must have .depends_on)
        self._adj: dict[str, list[str]] = defaultdict(list)   # upstream → [downstream]

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_node(self, node: Any) -> None:
        if node.node_id in self._nodes:
            raise ValueError(f"Duplicate node id: '{node.node_id}'")
        self._nodes[node.node_id] = node
        for dep in node.depends_on:
            self._adj[dep].append(node.node_id)

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def topological_order(self) -> list[list[str]]:
        """Return nodes grouped into levels (each level can run in parallel).

        Uses Kahn's algorithm. Raises CycleDetectedError if a cycle is found.
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    raise ValueError(f"Node '{node.node_id}' depends on unknown '{dep}'")
                in_degree[node.node_id] += 1

        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        levels: list[list[str]] = []
        visited = 0

        while queue:
            # All nodes currently in the queue share the same "level"
            level = list(queue)
            levels.append(level)
            queue.clear()
            for nid in level:
                visited += 1
                for downstream in self._adj.get(nid, []):
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        queue.append(downstream)

        if visited != len(self._nodes):
            cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
            raise CycleDetectedError(f"Cycle detected involving: {cycle_nodes}")

        return levels

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        context: dict[str, Any],
        completed_nodes: set[str] | None = None,
        on_node_start: Any = None,
        on_node_done: Any = None,
        on_node_error: Any = None,
    ) -> dict[str, Any]:
        """Execute the DAG, updating *context* in place as each node finishes.

        Args:
            context: shared data dict; each node reads inputs from and writes
                     outputs into this dict.
            completed_nodes: set of node_ids already done (for resume/checkpoint).
            on_node_start/on_node_done/on_node_error: optional async callbacks.
        """
        completed_nodes = completed_nodes or set()
        levels = self.topological_order()

        for level in levels:
            # Filter out already-completed nodes (checkpoint resume)
            pending = [nid for nid in level if nid not in completed_nodes]
            if not pending:
                continue

            # Run all nodes in this level concurrently
            tasks = [
                self._run_node(
                    self._nodes[nid],
                    context,
                    on_node_start,
                    on_node_done,
                    on_node_error,
                )
                for nid in pending
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for nid, result in zip(pending, results):
                if isinstance(result, BaseException):
                    logger.error("Node '%s' raised: %s", nid, result)
                    raise result  # propagate first failure

            logger.debug("Level completed: %s", pending)

        return context

    async def _run_node(
        self,
        node: Any,
        context: dict[str, Any],
        on_start: Any,
        on_done: Any,
        on_error: Any,
    ) -> None:
        node_id = node.node_id
        logger.info("Starting node '%s' (%s)", node_id, node.node_type)

        if on_start:
            await on_start(node_id)

        try:
            output = await node.execute(context)
            if output:
                context.update(output)
            context.setdefault("_completed", set()).add(node_id)
            logger.info("Node '%s' completed", node_id)
            if on_done:
                await on_done(node_id, output)
        except Exception as exc:
            logger.error("Node '%s' failed: %s", node_id, exc)
            if on_error:
                await on_error(node_id, exc)
            raise
