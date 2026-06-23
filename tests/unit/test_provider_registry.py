"""Tests for ProviderRegistry."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from aeep.core.exceptions import AllProvidersFailedError, ProviderNotFoundError
from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message, Role, StreamChunk
from aeep.providers.base import BaseLLMProvider
from aeep.providers.registry import ProviderRegistry, reset_registry


class _FakeProvider(BaseLLMProvider):
    """Minimal provider for testing  Ealways returns a canned response."""

    provider_type = ProviderType.API
    supported_models = ["fake-model"]

    def __init__(self, name: str, *, should_fail: bool = False) -> None:
        super().__init__(name=name, display_name=f"Fake {name}")
        self.should_fail = should_fail
        self.call_count = 0

    async def complete(self, messages, model="fake-model", temperature=0.7, max_tokens=4096, **kw):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("simulated failure")
        return CompletionResult(
            content="fake response",
            model=model,
            provider_name=self.name,
            input_tokens=10,
            output_tokens=5,
            finish_reason="stop",
            duration_ms=50,
        )

    async def stream(self, messages, model="fake-model", temperature=0.7, max_tokens=4096, **kw):
        async def _gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(delta="fake", is_final=True, finish_reason="stop")

        return _gen()

    async def count_tokens(self, messages):
        return sum(len(m.content.split()) for m in messages)

    async def health_check(self):
        if self.should_fail:
            return HealthCheckResult(HealthStatus.UNHEALTHY, message="simulated")
        return HealthCheckResult(HealthStatus.HEALTHY, latency_ms=10)

    def get_cost(self, input_tokens, output_tokens, model):
        return 0.0


@pytest.fixture(autouse=True)
def clean_registry():
    reset_registry()
    yield
    reset_registry()


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        p = _FakeProvider("alpha")
        registry.register(p)
        assert registry.get("alpha") is p

    def test_get_missing_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get("nonexistent")

    def test_list_all(self):
        registry = ProviderRegistry()
        registry.register(_FakeProvider("a"))
        registry.register(_FakeProvider("b"))
        names = {p.name for p in registry.list_all()}
        assert names == {"a", "b"}

    def test_get_by_type(self):
        registry = ProviderRegistry()
        p = _FakeProvider("api_p")
        registry.register(p)
        results = registry.get_by_type(ProviderType.API)
        assert p in results

    def test_overwrite_warns(self, caplog):
        import logging

        registry = ProviderRegistry()
        registry.register(_FakeProvider("dup"))
        with caplog.at_level(logging.WARNING):
            registry.register(_FakeProvider("dup"))
        assert any("Overwriting" in r.message for r in caplog.records)

    def test_unregister(self):
        registry = ProviderRegistry()
        registry.register(_FakeProvider("to_remove"))
        registry.unregister("to_remove")
        with pytest.raises(ProviderNotFoundError):
            registry.get("to_remove")

    def test_get_for_model(self):
        registry = ProviderRegistry()
        p = _FakeProvider("model_match")
        registry.register(p)
        found = registry.get_for_model("fake-model")
        assert found is p

    def test_get_for_model_no_match(self):
        registry = ProviderRegistry()
        registry.register(_FakeProvider("x"))
        result = registry.get_for_model("unknown-model-xyz")
        assert result is None


class TestFallbackComplete:
    @pytest.mark.asyncio
    async def test_primary_success(self):
        registry = ProviderRegistry()
        primary = _FakeProvider("primary")
        backup = _FakeProvider("backup")
        registry.register(primary)
        registry.register(backup)
        msgs = [Message(Role.USER, "hi")]
        result = await registry.complete_with_fallback(
            "primary", msgs, "fake-model", fallback_chain=["backup"]
        )
        assert result.provider_name == "primary"
        assert primary.call_count == 1
        assert backup.call_count == 0

    @pytest.mark.asyncio
    async def test_primary_fails_uses_fallback(self):
        registry = ProviderRegistry()
        primary = _FakeProvider("primary", should_fail=True)
        backup = _FakeProvider("backup")
        registry.register(primary)
        registry.register(backup)
        msgs = [Message(Role.USER, "hi")]
        result = await registry.complete_with_fallback(
            "primary", msgs, "fake-model", fallback_chain=["backup"]
        )
        assert result.provider_name == "backup"

    @pytest.mark.asyncio
    async def test_all_fail_raises(self):
        registry = ProviderRegistry()
        registry.register(_FakeProvider("p1", should_fail=True))
        registry.register(_FakeProvider("p2", should_fail=True))
        msgs = [Message(Role.USER, "hi")]
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await registry.complete_with_fallback(
                "p1", msgs, "fake-model", fallback_chain=["p2"]
            )
        assert "p1" in exc_info.value.errors
        assert "p2" in exc_info.value.errors


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        registry = ProviderRegistry()
        registry.register(_FakeProvider("flaky", should_fail=True))
        registry.register(_FakeProvider("stable"))
        msgs = [Message(Role.USER, "hi")]

        # trigger 3 failures to open circuit on "flaky"
        for _ in range(3):
            try:
                await registry.complete_with_fallback("flaky", msgs, "fake-model")
            except AllProvidersFailedError:
                pass

        breaker = registry._breakers["flaky"]
        assert breaker._state == "OPEN"
