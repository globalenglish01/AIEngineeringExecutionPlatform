"""BaseAPIProvider — shared HTTP logic for all REST-based LLM providers."""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message, Role
from aeep.providers.base import BaseLLMProvider

if TYPE_CHECKING:
    pass


class BaseAPIProvider(BaseLLMProvider):
    """Common plumbing for providers that call external REST APIs."""

    provider_type = ProviderType.API

    # Subclasses declare pricing as: {model: (input_per_1k, output_per_1k)} in USD
    PRICING: dict[str, tuple[float, float]] = {}

    def __init__(
        self,
        name: str,
        display_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(name=name, display_name=display_name)
        self._api_key = api_key or ""
        self._base_url = base_url

    # ------------------------------------------------------------------
    # get_cost — uses PRICING table
    # ------------------------------------------------------------------

    def get_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = self.PRICING.get(model)
        if not pricing:
            # fall back to first matching prefix
            for key, price in self.PRICING.items():
                if model.startswith(key):
                    pricing = price
                    break
        if not pricing:
            return 0.0
        input_cost = (input_tokens / 1000) * pricing[0]
        output_cost = (output_tokens / 1000) * pricing[1]
        return round(input_cost + output_cost, 8)

    # ------------------------------------------------------------------
    # health_check — lightweight ping
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            msg = Message(role=Role.USER, content="ping")
            await self.complete([msg], model=self._default_model(), max_tokens=1)
            latency = int((time.monotonic() - start) * 1000)
            return HealthCheckResult(HealthStatus.HEALTHY, latency_ms=latency)
        except Exception as exc:
            return HealthCheckResult(HealthStatus.UNHEALTHY, message=str(exc))
