"""OllamaProvider 窶・calls a locally-running Ollama service via its REST API."""

from __future__ import annotations

import json
import time
from typing import AsyncIterator

import httpx

from aeep.core.exceptions import ProviderError
from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message, StreamChunk
from aeep.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Wraps the Ollama /api/chat endpoint (non-OpenAI format)."""

    provider_type = ProviderType.LOCAL
    supported_models: list[str] = []  # populated from Ollama at runtime

    CONNECT_TIMEOUT = 5.0
    READ_TIMEOUT = 180.0

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
        name: str = "ollama",
        display_name: str = "Ollama (Local)",
    ) -> None:
        super().__init__(name=name, display_name=display_name)
        self._base_url = base_url.rstrip("/")
        self._model_name = default_model
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self.READ_TIMEOUT, connect=self.CONNECT_TIMEOUT),
        )

    def _default_model(self) -> str:  # type: ignore[override]
        return self._model_name

    def get_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        return 0.0

    async def count_tokens(self, messages: list[Message]) -> int:
        # Rough word-based estimate (no Ollama API for token counting)
        return int(sum(len(m.content.split()) for m in messages) * 1.35)

    async def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = await self._http.get("/api/tags", timeout=3.0)
            resp.raise_for_status()
            latency = int((time.monotonic() - start) * 1000)
            # Populate supported_models from the running Ollama instance
            data = resp.json()
            self.supported_models = [m["name"] for m in data.get("models", [])]
            return HealthCheckResult(HealthStatus.HEALTHY, latency_ms=latency)
        except Exception as exc:
            return HealthCheckResult(HealthStatus.UNHEALTHY, message=str(exc))

    async def complete(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult:
        _model = model or self._model_name
        start = time.monotonic()
        payload = {
            "model": _model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            resp = await self._http.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(self.name, str(exc)) from exc

        data = resp.json()
        duration_ms = int((time.monotonic() - start) * 1000)
        content = data.get("message", {}).get("content", "")
        return CompletionResult(
            content=content,
            model=_model,
            provider_name=self.name,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            finish_reason="stop",
            duration_ms=duration_ms,
            raw_response=data,
        )

    async def stream(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        _model = model or self._model_name

        async def _gen() -> AsyncIterator[StreamChunk]:
            payload = {
                "model": _model,
                "messages": [m.to_dict() for m in messages],
                "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            try:
                async with self._http.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk_data = json.loads(line)
                        delta = chunk_data.get("message", {}).get("content", "")
                        is_final = chunk_data.get("done", False)
                        yield StreamChunk(
                            delta=delta,
                            is_final=is_final,
                            finish_reason="stop" if is_final else None,
                        )
            except httpx.HTTPError as exc:
                raise ProviderError(self.name, str(exc)) from exc

        return _gen()
