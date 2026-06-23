"""Anthropic Provider — uses the official anthropic Python SDK."""

from __future__ import annotations

import time
from typing import AsyncIterator

from aeep.core.exceptions import ProviderError, ProviderRateLimitError
from aeep.core.models.message import CompletionResult, Message, Role, StreamChunk
from aeep.providers.api.base_api_provider import BaseAPIProvider

try:
    import anthropic

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


class AnthropicProvider(BaseAPIProvider):
    """Calls api.anthropic.com using the anthropic SDK."""

    supported_models = [
        "claude-sonnet-4-6",
        "claude-opus-4-8",
        "claude-haiku-4-5-20251001",
    ]

    PRICING: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-6":         (0.003, 0.015),
        "claude-opus-4-8":           (0.015, 0.075),
        "claude-haiku-4-5-20251001": (0.00025, 0.00125),
    }

    def __init__(
        self,
        api_key: str,
        name: str = "anthropic",
        display_name: str = "Anthropic Claude",
    ) -> None:
        super().__init__(name=name, display_name=display_name, api_key=api_key)
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required: uv add anthropic")
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=120.0)

    def _split_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict]]:
        """Anthropic uses a separate system param; extract it from messages."""
        system: str | None = None
        convo: list[dict] = []
        for m in messages:
            if m.role == Role.SYSTEM:
                system = m.content
            else:
                convo.append({"role": m.role.value, "content": m.content})
        return system, convo

    async def complete(
        self,
        messages: list[Message],
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult:
        start = time.monotonic()
        system, convo = self._split_messages(messages)
        try:
            extra: dict = {}
            if system:
                extra["system"] = system
            response = await self._client.messages.create(
                model=model,
                messages=convo,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
                **extra,
            )
        except anthropic.RateLimitError as exc:
            raise ProviderRateLimitError(self.name) from exc
        except anthropic.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        content = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        return CompletionResult(
            content=content,
            model=model,
            provider_name=self.name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
            duration_ms=duration_ms,
            raw_response={},
        )

    async def stream(
        self,
        messages: list[Message],
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        system, convo = self._split_messages(messages)

        async def _gen() -> AsyncIterator[StreamChunk]:
            try:
                extra: dict = {}
                if system:
                    extra["system"] = system
                async with self._client.messages.stream(
                    model=model,
                    messages=convo,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **extra,
                ) as stream:
                    async for text in stream.text_stream:
                        yield StreamChunk(delta=text, is_final=False)
                    yield StreamChunk(delta="", is_final=True, finish_reason="stop")
            except anthropic.RateLimitError as exc:
                raise ProviderRateLimitError(self.name) from exc
            except anthropic.APIError as exc:
                raise ProviderError(self.name, str(exc)) from exc

        return _gen()

    async def count_tokens(self, messages: list[Message]) -> int:
        # Rough estimate: ~1.3 tokens per word (Claude tokenizer approximation)
        total = sum(len(m.content.split()) for m in messages)
        return int(total * 1.3) + len(messages) * 4
