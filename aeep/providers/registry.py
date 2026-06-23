"""ProviderRegistry  Eglobal singleton for provider registration, discovery, and routing."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aeep.core.exceptions import (
    AllProvidersFailedError,
    CircuitBreakerOpenError,
    ProviderNotFoundError,
)
from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message

if TYPE_CHECKING:
    from aeep.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class _CircuitBreaker:
    """Per-provider circuit breaker (CLOSED ↁEOPEN ↁEHALF_OPEN ↁECLOSED)."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60) -> None:
        self._failures = 0
        self._state = "CLOSED"
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._state == "OPEN":
            import time

            if time.monotonic() - (self._opened_at or 0) >= self._recovery_timeout:
                self._state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._state = "CLOSED"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            import time

            self._state = "OPEN"
            self._opened_at = time.monotonic()


class ProviderRegistry:
    """Central registry for all LLM providers."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseLLMProvider] = {}
        self._breakers: dict[str, _CircuitBreaker] = {}
        self._health_cache: dict[str, HealthCheckResult] = {}
        self._monitor_task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, provider: BaseLLMProvider) -> None:
        if provider.name in self._providers:
            logger.warning("Overwriting provider '%s'", provider.name)
        self._providers[provider.name] = provider
        self._breakers[provider.name] = _CircuitBreaker()
        logger.info("Registered provider '%s' (%s)", provider.name, provider.provider_type)

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)
        self._breakers.pop(name, None)
        self._health_cache.pop(name, None)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseLLMProvider:
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._providers[name]

    def get_by_type(self, provider_type: ProviderType) -> list[BaseLLMProvider]:
        return [p for p in self._providers.values() if p.provider_type == provider_type]

    def get_for_model(self, model: str) -> BaseLLMProvider | None:
        candidates = [
            p
            for p in self._providers.values()
            if not p.supported_models or model in p.supported_models
        ]
        # prefer healthy providers
        for p in candidates:
            health = self._health_cache.get(p.name)
            if health and health.status == HealthStatus.HEALTHY:
                return p
        return candidates[0] if candidates else None

    def list_all(self) -> list[BaseLLMProvider]:
        return list(self._providers.values())

    # ------------------------------------------------------------------
    # Fallback-aware complete
    # ------------------------------------------------------------------

    async def complete_with_fallback(
        self,
        primary: str,
        messages: list[Message],
        model: str,
        fallback_chain: list[str] | None = None,
        **kwargs: object,
    ) -> CompletionResult:
        chain = [primary] + (fallback_chain or [])
        errors: dict[str, str] = {}

        for name in chain:
            try:
                provider = self.get(name)
                breaker = self._breakers[name]

                if breaker.is_open:
                    errors[name] = "circuit breaker OPEN"
                    raise CircuitBreakerOpenError(name, "circuit breaker OPEN")

                result = await provider.complete(messages, model, **kwargs)
                breaker.record_success()
                return result

            except ProviderNotFoundError as exc:
                errors[name] = str(exc)
            except Exception as exc:
                errors[name] = str(exc)
                if name in self._breakers:
                    self._breakers[name].record_failure()
                logger.warning("Provider '%s' failed: %s", name, exc)

        raise AllProvidersFailedError(errors)

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def start_health_monitoring(self, interval: int = 60) -> None:
        async def _loop() -> None:
            while True:
                await self._run_health_checks()
                await asyncio.sleep(interval)

        self._monitor_task = asyncio.create_task(_loop())

    async def _run_health_checks(self) -> None:
        for name, provider in self._providers.items():
            try:
                result = await provider.health_check()
                self._health_cache[name] = result
            except Exception as exc:
                self._health_cache[name] = HealthCheckResult(
                    HealthStatus.UNHEALTHY, message=str(exc)
                )

    def get_health(self, name: str) -> HealthCheckResult | None:
        return self._health_cache.get(name)

    def stop_health_monitoring(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None


# Global singleton
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry() -> None:
    """For testing only  Eresets the global singleton."""
    global _registry
    _registry = None
