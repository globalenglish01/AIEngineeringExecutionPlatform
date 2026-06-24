"""AccountPool — multi-account rotation for browser LLM providers.

When one account hits a rate/usage limit, the pool automatically switches
to the next available account and puts the exhausted one into a cooldown.

⚠️  Playwright imports are allowed in this directory.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeep.core.exceptions import ProviderRateLimitError
from aeep.core.models.message import CompletionResult, Message

logger = logging.getLogger(__name__)


class AllAccountsCoolingError(Exception):
    """Raised when every account in the pool is in cooldown."""

    def __init__(self, min_ready_at: float) -> None:
        self.min_ready_at = min_ready_at
        wait = max(0, int(min_ready_at - time.time()))
        super().__init__(f"All accounts are rate-limited. Earliest ready in {wait}s.")


@dataclass
class AccountSlot:
    index: int
    label: str
    cookie_path: str
    status: str = "未初始化"   # 未初始化 | 就绪 | 冷却中 | 已耗尽
    cooldown_until: float = 0.0
    provider: Any = field(default=None, repr=False)  # BrowserProvider

    # ------------------------------------------------------------------ helpers

    @property
    def is_ready(self) -> bool:
        if self.status == "冷却中" and time.time() >= self.cooldown_until:
            self.status = "就绪"
        return self.status == "就绪"

    @property
    def cooldown_remaining(self) -> int:
        return max(0, int(self.cooldown_until - time.time()))

    def mark_rate_limited(self, retry_after: int) -> None:
        self.status = "冷却中"
        self.cooldown_until = time.time() + retry_after
        logger.warning(
            "Account '%s' rate-limited — cooldown %ds (ready at %s)",
            self.label,
            retry_after,
            time.strftime("%H:%M:%S", time.localtime(self.cooldown_until)),
        )

    def to_dict(self) -> dict:
        cd = self.cooldown_remaining
        status_display = f"冷却中 ({cd}s)" if self.status == "冷却中" and cd > 0 else self.status
        return {
            "序号": self.index + 1,
            "账号": self.label,
            "状态": status_display,
            "Cookie": "✓ 已保存" if Path(self.cookie_path).exists() else "✗ 未保存",
        }


class AccountPool:
    """Manages N browser accounts for one target, with automatic rotation on rate limit."""

    def __init__(self, target: str, cookie_dir: Path) -> None:
        self.target = target
        self.cookie_dir = cookie_dir
        self._slots: list[AccountSlot] = []
        self._current_index = 0   # round-robin pointer

    # ------------------------------------------------------------------ public

    def slot_count(self) -> int:
        return len(self._slots)

    def slots(self) -> list[AccountSlot]:
        return list(self._slots)

    async def add_slot(self, label: str | None = None) -> AccountSlot:
        """Add a new account slot and open a browser window for login."""
        from aeep.providers.browser.browser_provider import BrowserProvider
        from aeep.providers.browser.session import BrowserConfig

        idx = len(self._slots)
        lbl = label or f"账号{idx + 1}"
        cookie_path = str(self.cookie_dir / f"{self.target}_{idx}.json")

        config = BrowserConfig(headless=False, cookie_path=cookie_path)
        provider = BrowserProvider(target=self.target, config=config,
                                   name=f"{self.target}_{idx}")
        await provider._ensure_initialized()

        # Navigate to the login page so the browser window is visible to the user
        page = await provider._session.get_page("login")
        await page.goto(
            provider._target.base_url,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await page.bring_to_front()

        slot = AccountSlot(index=idx, label=lbl, cookie_path=cookie_path,
                           status="就绪", provider=provider)
        self._slots.append(slot)
        logger.info("AccountPool[%s]: added slot '%s' (index=%d)", self.target, lbl, idx)
        return slot

    async def save_cookies(self, index: int) -> None:
        slot = self._slots[index]
        await slot.provider._session.save_cookies()
        logger.info("AccountPool[%s]: cookies saved for '%s'", self.target, slot.label)

    async def remove_slot(self, index: int) -> None:
        slot = self._slots[index]
        if slot.provider:
            await slot.provider.close()
        cookie = Path(slot.cookie_path)
        if cookie.exists():
            cookie.unlink()
        self._slots.pop(index)
        # Re-index remaining slots
        for i, s in enumerate(self._slots):
            s.index = i
        self._current_index = min(self._current_index, max(0, len(self._slots) - 1))
        logger.info("AccountPool[%s]: removed slot '%s'", self.target, slot.label)

    async def complete(
        self,
        messages: list[Message],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> CompletionResult:
        """Try accounts round-robin; rotate on rate limit."""
        if not self._slots:
            raise RuntimeError("AccountPool is empty — add at least one account first.")

        tried = 0
        start_index = self._current_index

        while tried < len(self._slots):
            slot = self._slots[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._slots)
            tried += 1

            if not slot.is_ready:
                logger.debug("Skipping '%s' (status=%s)", slot.label, slot.status)
                continue

            try:
                logger.info("AccountPool[%s]: using '%s'", self.target, slot.label)
                result = await slot.provider.complete(
                    messages, model=model, temperature=temperature,
                    max_tokens=max_tokens, **kwargs
                )
                return result

            except ProviderRateLimitError as exc:
                slot.mark_rate_limited(exc.retry_after or 3600)
                # continue to next slot

        # All slots either cooling or exhausted
        ready_times = [s.cooldown_until for s in self._slots if s.cooldown_until > 0]
        min_ready = min(ready_times) if ready_times else time.time() + 3600
        raise AllAccountsCoolingError(min_ready)

    def status_table(self) -> list[dict]:
        return [s.to_dict() for s in self._slots]
