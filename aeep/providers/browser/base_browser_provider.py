"""BaseBrowserProvider — LLMProvider implementation backed by a Playwright browser session.

⚠️  Playwright imports are allowed in this file (browser/ directory).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import AsyncIterator

from aeep.core.exceptions import (
    BrowserInitError,
    BrowserRateLimitError,
    BrowserSessionError,
    ProviderError,
    ProviderRateLimitError,
)
from aeep.core.interfaces.provider import HealthCheckResult, HealthStatus, ProviderType
from aeep.core.models.message import CompletionResult, Message, Role, StreamChunk
from aeep.providers.base import BaseLLMProvider
from aeep.providers.browser.session import BrowserConfig, BrowserSession
from aeep.providers.browser.targets.base_target import BaseBrowserTarget

logger = logging.getLogger(__name__)

_TIKTOKEN_ENCODING = "cl100k_base"


def _estimate_tokens(messages: list[Message]) -> int:
    """Token count estimate without calling the API (Browser providers only)."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding(_TIKTOKEN_ENCODING)
        return sum(len(enc.encode(m.content)) + 4 for m in messages) + 2
    except Exception:
        return sum(len(m.content.split()) * 13 // 10 for m in messages)


class BaseBrowserProvider(BaseLLMProvider):
    """Common logic for all browser-backed LLM providers."""

    provider_type = ProviderType.BROWSER
    supported_models: list[str] = []

    def __init__(
        self,
        target: BaseBrowserTarget,
        config: BrowserConfig,
        name: str,
        display_name: str,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        super().__init__(name=name, display_name=display_name)
        self._target = target
        self._config = config
        self._session = BrowserSession(config)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._session_map: dict[str, str] = {}  # conversation_id → page session_id

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def get_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        return 0.0  # web browser access is free

    async def count_tokens(self, messages: list[Message]) -> int:
        return _estimate_tokens(messages)

    async def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            await self._ensure_initialized()
            page = await self._session.get_page("_health")
            await page.goto(self._target.base_url, wait_until="domcontentloaded", timeout=15_000)
            logged_in = await self._target.is_logged_in(page)
            latency = int((time.monotonic() - start) * 1000)
            if logged_in:
                return HealthCheckResult(HealthStatus.HEALTHY, latency_ms=latency)
            return HealthCheckResult(
                HealthStatus.DEGRADED,
                latency_ms=latency,
                message="Not logged in — manual login required",
            )
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
        start = time.monotonic()
        await self._ensure_initialized()

        prompt = self._messages_to_prompt(messages)
        session_id = str(uuid.uuid4())

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                page = await self._session.get_page(session_id)
                await self._target.navigate_to_new_chat(page)
                await self._target.send_message(page, prompt)
                raw_html = await self._target.wait_for_response(
                    page,
                    timeout_ms=int(max_tokens / 10 * 1000 + 60_000),
                )
                if not raw_html:
                    raise BrowserSessionError("Empty response from browser")

                extracted = await self._target.extract_response(raw_html)
                duration_ms = int((time.monotonic() - start) * 1000)

                input_tokens = _estimate_tokens(messages)
                output_tokens = _estimate_tokens(
                    [Message(role=Role.ASSISTANT, content=extracted.full_markdown)]
                )

                return CompletionResult(
                    content=extracted.full_markdown,
                    model=f"browser:{self._target.target_name}",
                    provider_name=self.name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    finish_reason="stop",
                    duration_ms=duration_ms,
                )

            except BrowserRateLimitError as exc:
                # Propagate rate limit immediately — AccountPool will rotate accounts
                raise ProviderRateLimitError(self.name, retry_after=exc.retry_after) from exc
            except BrowserSessionError as exc:
                last_exc = exc
                logger.warning(
                    "BrowserProvider attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * attempt)

        raise ProviderError(self.name, f"All {self._max_retries} attempts failed: {last_exc}")

    async def stream(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        """Browser providers don't support true streaming — complete() result is chunked."""

        async def _gen() -> AsyncIterator[StreamChunk]:
            result = await self.complete(messages, model, temperature, max_tokens, **kwargs)
            chunk_size = 200
            content = result.content
            for i in range(0, len(content), chunk_size):
                is_last = (i + chunk_size) >= len(content)
                yield StreamChunk(
                    delta=content[i : i + chunk_size],
                    is_final=is_last,
                    finish_reason="stop" if is_last else None,
                )

        return _gen()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        if not self._session._initialized:
            try:
                await self._session.initialize()
            except ImportError as exc:
                raise BrowserInitError(str(exc)) from exc

    def _messages_to_prompt(self, messages: list[Message]) -> str:
        """Flatten message list into a single prompt string for the web UI.

        System messages are prepended to the first user message rather than
        sent as a separate turn — browser UIs have no system-prompt field.
        """
        system_parts: list[str] = []
        non_system: list[Message] = []
        for m in messages:
            if m.role == Role.SYSTEM:
                system_parts.append(m.content)
            else:
                non_system.append(m)

        parts: list[str] = []
        first_user_done = False
        for m in non_system:
            if m.role == Role.USER:
                if not first_user_done and system_parts:
                    # Task FIRST, then instructions — helps browser LLMs focus on the task
                    system_block = "\n\n".join(system_parts)
                    parts.append(f"{m.content}\n\n---\n{system_block}")
                    first_user_done = True
                else:
                    parts.append(m.content)
            elif m.role == Role.ASSISTANT:
                parts.append(f"[Assistant]\n{m.content}")

        # Edge case: only system messages, no user turn yet
        if not parts and system_parts:
            parts.append("\n\n".join(system_parts))

        return "\n\n".join(parts)

    async def close(self) -> None:
        await self._session.close()
