"""LLMProvider interface  Eall provider implementations must satisfy this protocol."""

from __future__ import annotations

from enum import Enum
from typing import AsyncIterator, Protocol, runtime_checkable

from aeep.core.models.message import CompletionResult, Message, StreamChunk


class ProviderType(str, Enum):
    API = "api"
    LOCAL = "local"
    BROWSER = "browser"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    __slots__ = ("status", "latency_ms", "message")

    def __init__(
        self,
        status: HealthStatus,
        latency_ms: int | None = None,
        message: str | None = None,
    ) -> None:
        self.status = status
        self.latency_ms = latency_ms
        self.message = message

    @property
    def is_available(self) -> bool:
        return self.status != HealthStatus.UNHEALTHY


@runtime_checkable
class LLMProvider(Protocol):
    """Unified interface every provider must implement."""

    name: str             # globally unique identifier
    display_name: str     # human-readable name
    provider_type: ProviderType
    supported_models: list[str]  # empty list ↁEaccepts any model string

    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult: ...

    async def stream(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]: ...

    async def count_tokens(self, messages: list[Message]) -> int: ...

    async def health_check(self) -> HealthCheckResult: ...

    def get_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Return estimated cost in USD. Browser and local providers return 0.0."""
        ...
