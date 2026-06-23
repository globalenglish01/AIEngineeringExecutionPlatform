"""OpenAI Provider — uses the official openai Python SDK."""

from __future__ import annotations

import time
from typing import AsyncIterator

from aeep.core.exceptions import ProviderError, ProviderRateLimitError
from aeep.core.models.message import CompletionResult, Message, StreamChunk
from aeep.providers.api.base_api_provider import BaseAPIProvider

try:
    import openai
    import tiktoken

    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


class OpenAIProvider(BaseAPIProvider):
    """Calls api.openai.com using the openai SDK."""

    supported_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o1",
        "o1-mini",
        "o3-mini",
    ]

    PRICING: dict[str, tuple[float, float]] = {
        "gpt-4o":          (0.0025, 0.010),
        "gpt-4o-mini":     (0.00015, 0.0006),
        "gpt-4-turbo":     (0.010, 0.030),
        "o1":              (0.015, 0.060),
        "o1-mini":         (0.003, 0.012),
        "o3-mini":         (0.0011, 0.0044),
    }

    def __init__(
        self,
        api_key: str,
        name: str = "openai",
        display_name: str = "OpenAI",
        base_url: str | None = None,
    ) -> None:
        super().__init__(name=name, display_name=display_name, api_key=api_key, base_url=base_url)
        if not _OPENAI_AVAILABLE:
            raise ImportError("openai package is required: uv add openai")
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=120.0,
        )

    def _messages_to_openai(self, messages: list[Message]) -> list[dict]:
        return [m.to_dict() for m in messages]

    async def complete(
        self,
        messages: list[Message],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=self._messages_to_openai(messages),  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                **{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, list))},
            )
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(self.name) from exc
        except openai.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage

        return CompletionResult(
            content=choice.message.content or "",
            model=model,
            provider_name=self.name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop",
            duration_ms=duration_ms,
            raw_response=response.model_dump(),
        )

    async def stream(
        self,
        messages: list[Message],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        async def _gen() -> AsyncIterator[StreamChunk]:
            try:
                async with await self._client.chat.completions.create(
                    model=model,
                    messages=self._messages_to_openai(messages),  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ) as stream:
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        finish = chunk.choices[0].finish_reason
                        is_final = finish is not None
                        yield StreamChunk(delta=delta, is_final=is_final, finish_reason=finish)
            except openai.RateLimitError as exc:
                raise ProviderRateLimitError(self.name) from exc
            except openai.APIError as exc:
                raise ProviderError(self.name, str(exc)) from exc

        return _gen()

    async def count_tokens(self, messages: list[Message]) -> int:
        try:
            enc = tiktoken.encoding_for_model(self._resolve_tiktoken_model())
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            total += 4  # per-message overhead
            total += len(enc.encode(m.content))
        return total + 2  # reply priming

    def _resolve_tiktoken_model(self) -> str:
        # tiktoken uses model aliases
        return "gpt-4o"
