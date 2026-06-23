"""BaseNode — common interface and plumbing for all workflow nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseNode(ABC):
    """Every workflow node must inherit from this class."""

    node_type: str = "base"

    def __init__(
        self,
        node_id: str,
        depends_on: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.depends_on: list[str] = depends_on or []
        self.config: dict[str, Any] = config or {}

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run this node, reading from *context* and returning new key-value pairs."""
        ...

    def _get(self, context: dict[str, Any], key: str, default: Any = None) -> Any:
        """Convenience: read a key from context with an optional default."""
        return context.get(key, self.config.get(key, default))
