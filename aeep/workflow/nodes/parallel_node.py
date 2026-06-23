"""ParallelNode — runs sub-nodes concurrently and aggregates results."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class ParallelNode(BaseNode):
    """Executes a list of inner nodes in parallel (asyncio.gather) and merges outputs.

    Config keys:
        output_key      str   context key for aggregated list of results (default: node_id)
        fail_fast       bool  if True, cancel all on first failure (default: False)
    """

    node_type = "parallel"

    def __init__(
        self,
        node_id: str,
        inner_nodes: list[BaseNode],
        depends_on: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_id, depends_on, config)
        self._inner_nodes = inner_nodes

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        fail_fast: bool = bool(self.config.get("fail_fast", False))
        output_key: str = self.config.get("output_key", self.node_id)

        logger.info(
            "ParallelNode '%s': running %d inner nodes concurrently",
            self.node_id,
            len(self._inner_nodes),
        )

        # Each inner node gets a shallow copy of context so they don't trample each other
        async def _run(node: BaseNode) -> dict[str, Any]:
            local_ctx = dict(context)
            result = await node.execute(local_ctx)
            return result or {}

        if fail_fast:
            results = await asyncio.gather(*[_run(n) for n in self._inner_nodes])
        else:
            results = await asyncio.gather(
                *[_run(n) for n in self._inner_nodes],
                return_exceptions=True,
            )

        merged: dict[str, Any] = {}
        errors: list[str] = []
        outputs: list[Any] = []

        for node, result in zip(self._inner_nodes, results):
            if isinstance(result, BaseException):
                logger.error("ParallelNode inner node '%s' failed: %s", node.node_id, result)
                errors.append(f"{node.node_id}: {result}")
            else:
                merged.update(result)
                outputs.append(result)

        merged[output_key] = outputs
        if errors:
            merged[f"{self.node_id}_errors"] = errors

        logger.info(
            "ParallelNode '%s': %d succeeded, %d failed",
            self.node_id,
            len(outputs),
            len(errors),
        )

        return merged
