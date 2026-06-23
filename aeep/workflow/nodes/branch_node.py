"""BranchNode — conditional branching based on context values."""

from __future__ import annotations

import logging
from typing import Any

from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class BranchNode(BaseNode):
    """Evaluates a condition and sets a branch key for downstream nodes.

    Config keys:
        condition_key   str   context key to test (required)
        condition_op    str   "truthy" | "eq" | "gt" | "lt" | "contains" (default: "truthy")
        condition_value any   value to compare against (for eq/gt/lt)
        true_branch     str   value written to output_key when condition is True
        false_branch    str   value written to output_key when condition is False
        output_key      str   context key to write branch result (default: node_id)
    """

    node_type = "branch"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        condition_key: str = self.config.get("condition_key", "")
        condition_op: str = self.config.get("condition_op", "truthy")
        condition_value: Any = self.config.get("condition_value")
        true_branch: str = self.config.get("true_branch", "true")
        false_branch: str = self.config.get("false_branch", "false")
        output_key: str = self.config.get("output_key", self.node_id)

        actual = context.get(condition_key)
        result = self._evaluate(actual, condition_op, condition_value)
        branch = true_branch if result else false_branch

        logger.info(
            "BranchNode '%s': %s %s %s → %s",
            self.node_id,
            condition_key,
            condition_op,
            condition_value,
            branch,
        )

        return {output_key: branch, f"{self.node_id}_condition": result}

    @staticmethod
    def _evaluate(actual: Any, op: str, expected: Any) -> bool:
        if op == "truthy":
            return bool(actual)
        if op == "eq":
            return actual == expected
        if op == "gt":
            return float(actual) > float(expected)
        if op == "lt":
            return float(actual) < float(expected)
        if op == "contains":
            return str(expected) in str(actual)
        raise ValueError(f"Unknown condition_op: '{op}'")
