"""Tests for the retry utility."""

from __future__ import annotations

import pytest

from aeep.workflow.retry import is_retryable, retry_async
from aeep.core.exceptions import ConfigError, QualityGateFailedError


class TestIsRetryable:
    def test_runtime_error_is_retryable(self):
        assert is_retryable(RuntimeError("network error")) is True

    def test_config_error_not_retryable(self):
        assert is_retryable(ConfigError("bad config")) is False

    def test_value_error_not_retryable(self):
        assert is_retryable(ValueError("bad value")) is False

    def test_quality_gate_not_retryable(self):
        exc = QualityGateFailedError("gate", 50.0, 70.0)
        assert is_retryable(exc) is False


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        calls = []

        async def _fn() -> str:
            calls.append(1)
            return "ok"

        result = await retry_async(_fn, max_attempts=3, initial_delay=0.01)
        assert result == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_retry(self):
        attempts = []

        async def _fn() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("transient")
            return "success"

        result = await retry_async(_fn, max_attempts=5, initial_delay=0.01, backoff_factor=1.0)
        assert result == "success"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        calls = []

        async def _fn() -> None:
            calls.append(1)
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError):
            await retry_async(_fn, max_attempts=3, initial_delay=0.01, backoff_factor=1.0)

        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_non_retryable_raises_immediately(self):
        calls = []

        async def _fn() -> None:
            calls.append(1)
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            await retry_async(_fn, max_attempts=3, initial_delay=0.01)

        assert len(calls) == 1  # no retry

    @pytest.mark.asyncio
    async def test_rate_limit_uses_retry_after(self):
        from aeep.core.exceptions import ProviderRateLimitError

        delays: list[float] = []
        original_sleep = __import__("asyncio").sleep

        async def _fake_sleep(delay: float) -> None:
            delays.append(delay)

        import asyncio
        asyncio.sleep = _fake_sleep

        calls = []

        async def _fn() -> str:
            calls.append(1)
            if len(calls) == 1:
                raise ProviderRateLimitError("p", retry_after=5)
            return "ok"

        try:
            result = await retry_async(_fn, max_attempts=3, initial_delay=1.0)
            assert result == "ok"
            assert delays[0] == 5  # used retry_after
        finally:
            asyncio.sleep = original_sleep
