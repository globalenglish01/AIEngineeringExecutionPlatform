"""Unit tests for providers — no real API calls, no real browser."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeep.core.exceptions import ProviderError
from aeep.core.interfaces.provider import ProviderType
from aeep.core.models.message import Message, Role
from aeep.providers.cost_tracker import CostRecord, CostTracker
from aeep.providers.fallback import FallbackChain
from aeep.providers.local.ollama_provider import OllamaProvider
from aeep.providers.registry import ProviderRegistry, reset_registry


# ---------------------------------------------------------------------------
# OllamaProvider unit tests (mock httpx)
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    def test_get_cost_is_zero(self):
        p = OllamaProvider()
        assert p.get_cost(100, 200, "llama3") == 0.0

    def test_provider_type(self):
        p = OllamaProvider()
        assert p.provider_type == ProviderType.LOCAL

    @pytest.mark.asyncio
    async def test_count_tokens_estimate(self):
        p = OllamaProvider()
        msgs = [Message(Role.USER, "hello world foo bar")]
        tokens = await p.count_tokens(msgs)
        assert tokens > 0

    @pytest.mark.asyncio
    async def test_complete_success(self):
        p = OllamaProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Hello, I am Llama!"},
            "prompt_eval_count": 10,
            "eval_count": 8,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(p._http, "post", new=AsyncMock(return_value=mock_response)):
            msgs = [Message(Role.USER, "hi")]
            result = await p.complete(msgs, model="llama3")
            assert result.content == "Hello, I am Llama!"
            assert result.input_tokens == 10
            assert result.output_tokens == 8
            assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        import httpx

        p = OllamaProvider()
        with patch.object(p._http, "get", side_effect=httpx.ConnectError("refused")):
            result = await p.health_check()
            from aeep.core.interfaces.provider import HealthStatus

            assert result.status == HealthStatus.UNHEALTHY


# ---------------------------------------------------------------------------
# Cost Tracker tests
# ---------------------------------------------------------------------------


class TestCostTracker:
    def test_record_and_summary(self, tmp_path: Path):
        db = tmp_path / "test.db"
        tracker = CostTracker(db_path=db)

        tracker.record(
            CostRecord(
                provider_name="openai",
                model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                duration_ms=300,
                task_type="book_chapter",
            )
        )
        tracker.record(
            CostRecord(
                provider_name="deepseek",
                model="deepseek-chat",
                input_tokens=200,
                output_tokens=100,
                cost_usd=0.0002,
                duration_ms=800,
            )
        )

        summary = tracker.get_summary()
        assert summary.total_calls == 2
        assert abs(summary.total_cost_usd - 0.0012) < 1e-9
        assert "openai" in summary.by_provider
        assert "book_chapter" in summary.by_task_type

    def test_filter_by_provider(self, tmp_path: Path):
        db = tmp_path / "test.db"
        tracker = CostTracker(db_path=db)
        tracker.record(
            CostRecord(
                provider_name="openai", model="gpt-4o",
                input_tokens=10, output_tokens=5, cost_usd=0.01, duration_ms=100,
            )
        )
        tracker.record(
            CostRecord(
                provider_name="anthropic", model="claude-sonnet-4-6",
                input_tokens=10, output_tokens=5, cost_usd=0.02, duration_ms=200,
            )
        )
        summary = tracker.get_summary(provider="openai")
        assert summary.total_calls == 1
        assert abs(summary.total_cost_usd - 0.01) < 1e-9

    def test_get_today_cost(self, tmp_path: Path):
        db = tmp_path / "test.db"
        tracker = CostTracker(db_path=db)
        tracker.record(
            CostRecord(
                provider_name="openai", model="gpt-4o",
                input_tokens=10, output_tokens=5, cost_usd=0.05, duration_ms=100,
            )
        )
        assert tracker.get_today_cost() == pytest.approx(0.05)

    def test_schema_idempotent(self, tmp_path: Path):
        db = tmp_path / "test.db"
        CostTracker(db_path=db)
        CostTracker(db_path=db)  # second init should not fail


# ---------------------------------------------------------------------------
# FallbackChain tests
# ---------------------------------------------------------------------------


class _OkProvider:
    name = "ok"
    _breakers: dict = {}

    async def complete(self, messages, model, **kwargs):
        from aeep.core.models.message import CompletionResult

        return CompletionResult(
            content="ok", model=model, provider_name="ok",
            input_tokens=5, output_tokens=5, finish_reason="stop", duration_ms=10,
        )


class _FailProvider:
    name = "fail"
    _breakers: dict = {}

    async def complete(self, messages, model, **kwargs):
        raise ProviderError("fail", "simulated failure")


class TestFallbackChain:
    def _make_registry_stub(self, providers: dict) -> ProviderRegistry:
        """Minimal stub that supports get() and _breakers."""
        reg = MagicMock(spec=ProviderRegistry)
        reg._breakers = {}
        reg.get = lambda name: providers[name]
        return reg

    @pytest.mark.asyncio
    async def test_first_provider_success(self):
        providers = {"ok": _OkProvider(), "fallback": _OkProvider()}
        reg = self._make_registry_stub(providers)
        chain = FallbackChain(reg, ["ok", "fallback"])
        msgs = [Message(Role.USER, "hi")]
        result = await chain.complete(msgs, "any-model")
        assert result.content == "ok"

    @pytest.mark.asyncio
    async def test_falls_back_on_error(self):
        providers = {"fail": _FailProvider(), "ok": _OkProvider()}
        reg = self._make_registry_stub(providers)
        chain = FallbackChain(reg, ["fail", "ok"])
        msgs = [Message(Role.USER, "hi")]
        result = await chain.complete(msgs, "any-model")
        assert result.provider_name == "ok"

    @pytest.mark.asyncio
    async def test_all_fail_raises(self):
        from aeep.core.exceptions import AllProvidersFailedError

        providers = {"f1": _FailProvider(), "f2": _FailProvider()}
        reg = self._make_registry_stub(providers)
        chain = FallbackChain(reg, ["f1", "f2"])
        msgs = [Message(Role.USER, "hi")]
        with pytest.raises(AllProvidersFailedError):
            await chain.complete(msgs, "any-model")

    def test_empty_chain_raises(self):
        reg = MagicMock()
        with pytest.raises(ValueError):
            FallbackChain(reg, [])


# ---------------------------------------------------------------------------
# Browser Provider — target extraction unit tests (no browser required)
# ---------------------------------------------------------------------------


class TestChatGPTTargetExtraction:
    @pytest.mark.asyncio
    async def test_extract_plain_text(self):
        from aeep.providers.browser.targets.chatgpt import ChatGPTTarget

        target = ChatGPTTarget()
        html = "<div>Hello, this is a plain response.</div>"
        result = await target.extract_response(html)
        assert "Hello" in result.plain_text
        assert result.code_blocks == []

    @pytest.mark.asyncio
    async def test_extract_code_block(self):
        from aeep.providers.browser.targets.chatgpt import ChatGPTTarget

        target = ChatGPTTarget()
        html = (
            "<div>Here is code:</div>"
            "<pre><code class='language-python'>print('hello')</code></pre>"
        )
        result = await target.extract_response(html)
        assert len(result.code_blocks) == 1
        assert result.code_blocks[0]["language"] == "python"
        assert "print" in result.code_blocks[0]["code"]

    @pytest.mark.asyncio
    async def test_full_markdown_reconstruction(self):
        from aeep.providers.browser.targets.chatgpt import ChatGPTTarget

        target = ChatGPTTarget()
        html = (
            "<div>Explanation</div>"
            "<pre><code class='language-bash'>echo hi</code></pre>"
        )
        result = await target.extract_response(html)
        md = result.full_markdown
        assert "```bash" in md
        assert "echo hi" in md


class TestDeepSeekTargetExtraction:
    @pytest.mark.asyncio
    async def test_extract_plain(self):
        from aeep.providers.browser.targets.deepseek import DeepSeekTarget

        target = DeepSeekTarget()
        html = "<div class='ds-markdown'>Simple answer.</div>"
        result = await target.extract_response(html)
        assert "Simple answer" in result.plain_text


class TestBaseBrowserProviderTokenEstimate:
    def test_estimate_tokens(self):
        from aeep.providers.browser.base_browser_provider import _estimate_tokens

        msgs = [Message(Role.USER, "Hello world, this is a test message for token counting.")]
        tokens = _estimate_tokens(msgs)
        assert tokens > 0

    def test_messages_to_prompt(self):
        from unittest.mock import MagicMock

        from aeep.providers.browser.base_browser_provider import BaseBrowserProvider

        # We can't fully instantiate without a target, but we can test _messages_to_prompt
        # by calling it as an unbound method with a mock self
        provider = MagicMock(spec=BaseBrowserProvider)
        provider._messages_to_prompt = BaseBrowserProvider._messages_to_prompt.__get__(
            provider, BaseBrowserProvider
        )
        msgs = [
            Message(Role.SYSTEM, "You are a helpful assistant"),
            Message(Role.USER, "Hello"),
        ]
        prompt = provider._messages_to_prompt(msgs)
        assert "[System]" in prompt
        assert "You are a helpful assistant" in prompt
        assert "Hello" in prompt
