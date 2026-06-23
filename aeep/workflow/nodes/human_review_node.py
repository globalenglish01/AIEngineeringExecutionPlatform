"""HumanReviewNode — pauses workflow and waits for human input."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class HumanReviewNode(BaseNode):
    """Pauses execution and waits for human approval.

    Config keys:
        prompt_message   str   message shown to the reviewer
        timeout_seconds  int   seconds to wait before auto-action (default: 3600)
        timeout_action   str   "approve" | "reject" on timeout (default: "approve")
        input_key        str   context key with content to review
        output_key       str   where to store decision (default: node_id)
    """

    node_type = "human_review"

    # Callback registry: maps node_id → asyncio.Future for external systems to resolve
    _pending: dict[str, asyncio.Future] = {}  # type: ignore[type-arg]

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        timeout: int = int(self.config.get("timeout_seconds", 3600))
        timeout_action: str = self.config.get("timeout_action", "approve")
        prompt_msg: str = self.config.get(
            "prompt_message",
            f"[HumanReview] Node '{self.node_id}' awaiting review. "
            f"Call HumanReviewNode.resolve('{self.node_id}', approved=True/False).",
        )
        output_key: str = self.config.get("output_key", self.node_id)

        logger.info("HumanReviewNode '%s': waiting for review (timeout=%ds)", self.node_id, timeout)
        print(f"\n{prompt_msg}\n")  # visible in CLI

        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        HumanReviewNode._pending[self.node_id] = future

        try:
            approved: bool = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            approved = timeout_action == "approve"
            logger.warning(
                "HumanReviewNode '%s': timed out → %s",
                self.node_id,
                "approved" if approved else "rejected",
            )
        finally:
            HumanReviewNode._pending.pop(self.node_id, None)

        logger.info("HumanReviewNode '%s': %s", self.node_id, "approved" if approved else "rejected")

        if not approved:
            raise RuntimeError(f"Human review rejected node '{self.node_id}'")

        return {output_key: {"approved": approved, "node_id": self.node_id}}

    @classmethod
    def resolve(cls, node_id: str, approved: bool) -> bool:
        """External code calls this to unblock a waiting HumanReviewNode."""
        future = cls._pending.get(node_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False
