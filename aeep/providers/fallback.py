"""FallbackChain — ordered list of providers with automatic failover."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aeep.core.exceptions import AllProvidersFailedError, ProviderError
from aeep.core.models.message import CompletionResult, Message

if TYPE_CHECKING:
    from aeep.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class FallbackChain:
    """Execute a request against an ordered provider chain; stop at first success."""

    def __init__(self, registry: ProviderRegistry, chain: list[str]) -> None:
        if not chain:
            raise ValueError("FallbackChain requires at least one provider name")
        self._registry = registry
        self._chain = chain

    async def complete(
        self,
        messages: list[Message],
        model: str,
        **kwargs: object,
    ) -> CompletionResult:
        errors: dict[str, str] = {}

        for name in self._chain:
            try:
                provider = self._registry.get(name)
                breaker = self._registry._breakers.get(name)

                if breaker and breaker.is_open:
                    errors[name] = "circuit breaker OPEN"
                    logger.info("Skipping '%s' — circuit breaker OPEN", name)
                    continue

                result = await provider.complete(messages, model, **kwargs)
                if breaker:
                    breaker.record_success()
                logger.info("FallbackChain: '%s' succeeded", name)
                return result

            except ProviderError as exc:
                errors[name] = str(exc)
                if name in self._registry._breakers:
                    self._registry._breakers[name].record_failure()
                logger.warning("FallbackChain: '%s' failed — %s", name, exc)
            except Exception as exc:
                errors[name] = str(exc)
                if name in self._registry._breakers:
                    self._registry._breakers[name].record_failure()
                logger.warning("FallbackChain: '%s' unexpected error — %s", name, exc)

        raise AllProvidersFailedError(errors)
