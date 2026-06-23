"""LoopNode — iterates inner nodes until a condition is met or max iterations reached."""

from __future__ import annotations

import logging
from typing import Any

from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class LoopNode(BaseNode):
    """Runs a sub-DAG repeatedly until exit_condition is True or max_iterations.

    Config keys:
        max_iterations  int   hard cap on loop iterations (default: 5)
        exit_key        str   context key to check for loop exit (default: "{node_id}_passed")
        inner_nodes     list  list of BaseNode instances to run each iteration
        output_key      str   context key to store final iteration count
    """

    node_type = "loop"

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
        max_iter: int = int(self.config.get("max_iterations", 5))
        exit_key: str = self.config.get("exit_key", f"{self.node_id}_passed")
        output_key: str = self.config.get("output_key", self.node_id)

        for iteration in range(1, max_iter + 1):
            context["_iteration"] = iteration
            logger.info("LoopNode '%s': iteration %d/%d", self.node_id, iteration, max_iter)

            for node in self._inner_nodes:
                result = await node.execute(context)
                if result:
                    context.update(result)

            if context.get(exit_key):
                logger.info("LoopNode '%s': exit condition met at iteration %d", self.node_id, iteration)
                return {output_key: {"iterations": iteration, "exit_reason": "condition_met"}}

        logger.warning("LoopNode '%s': max iterations (%d) reached", self.node_id, max_iter)
        return {output_key: {"iterations": max_iter, "exit_reason": "max_iterations"}}
