"""BaseLLMProvider  Econcrete base class with common logic for all providers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import AsyncIterator

from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message, StreamChunk


class BaseLLMProvider(ABC):
    """Abstract base class implementing shared provider plumbing."""

    provider_type: ProviderType
    supported_models: list[str] = []  # empty = accepts any

    def __init__(self, name: str, display_name: str) -> None:
        self.name = name
        self.display_name = display_name

    # ------------------------------------------------------------------
    # Subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    async def count_tokens(self, messages: list[Message]) -> int: ...

    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int, model: str) -> float: ...

    # ------------------------------------------------------------------
    # Default health_check  Esubclasses may override
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Basic health check: attempt a minimal complete call."""
        from aeep.core.models.message import Role

        start = time.monotonic()
        try:
            msg = Message(role=Role.USER, content="ping")
            await self.complete([msg], model=self._default_model(), max_tokens=1)
            latency = int((time.monotonic() - start) * 1000)
            return HealthCheckResult(HealthStatus.HEALTHY, latency_ms=latency)
        except Exception as exc:
            return HealthCheckResult(HealthStatus.UNHEALTHY, message=str(exc))

    def _default_model(self) -> str:
        return self.supported_models[0] if self.supported_models else "default"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} type={self.provider_type}>"
