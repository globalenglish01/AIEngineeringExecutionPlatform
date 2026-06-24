"""AccountPool — multi-account rotation with JSON persistence.

Accounts are saved to accounts.json so they survive app restarts / page refreshes.
Each account slot has its own Chrome persistent profile directory.

⚠️  Playwright imports are allowed in this directory.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeep.core.exceptions import ProviderRateLimitError

logger = logging.getLogger(__name__)

# Default profile base directory (same pattern as reference project)
_DEFAULT_PROFILE_BASE = Path.home() / "AppData" / "Roaming" / "AEEP" / "accounts"


class AllAccountsCoolingError(Exception):
    def __init__(self, min_ready_at: float) -> None:
        self.min_ready_at = min_ready_at
        wait = max(0, int(min_ready_at - time.time()))
        super().__init__(f"All accounts rate-limited. Earliest ready in {wait}s.")


@dataclass
class AccountSlot:
    id: str                      # unique id, e.g. "acc_a1b2c3d4"
    index: int
    label: str
    target: str
    user_data_dir: str           # persistent Chrome profile dir
    status: str = "ready"        # ready | cooling | exhausted
    cooldown_until: float = 0.0
    logged_in: bool = False
    provider: Any = field(default=None, repr=False)

    # ------------------------------------------------------------------ helpers

    @property
    def is_ready(self) -> bool:
        if self.status == "cooling" and time.time() >= self.cooldown_until:
            self.status = "ready"
        return self.status == "ready"

    @property
    def cooldown_remaining(self) -> int:
        return max(0, int(self.cooldown_until - time.time()))

    def mark_rate_limited(self, retry_after: int) -> None:
        self.status = "cooling"
        self.cooldown_until = time.time() + retry_after
        logger.warning("Account '%s' cooling for %ds", self.label, retry_after)

    def to_dict(self) -> dict:
        cd = self.cooldown_remaining
        if self.status == "cooling" and cd > 0:
            status_display = f"cooling ({cd}s)"
        else:
            status_display = self.status
        profile_exists = Path(self.user_data_dir).exists()
        return {
            "no": self.index + 1,
            "account": self.label,
            "status": status_display,
            "cookie": "saved" if profile_exists else "pending login",
        }

    def to_json(self) -> dict:
        """Serialisable form for accounts.json."""
        return {
            "id": self.id,
            "label": self.label,
            "target": self.target,
            "user_data_dir": self.user_data_dir,
            "logged_in": Path(self.user_data_dir).exists(),
        }


class AccountPool:
    """Manages N browser accounts for one target.

    State is persisted to accounts.json — survives Gradio page refreshes
    and app restarts.
    """

    def __init__(self, target: str, cookie_dir: Path, accounts_file: Path) -> None:
        self.target = target
        self.cookie_dir = cookie_dir
        self.accounts_file = accounts_file
        self._slots: list[AccountSlot] = []
        self._current_index = 0
        self._load()

    # ------------------------------------------------------------------ persistence

    def _load(self) -> None:
        """Load existing accounts from accounts.json on startup."""
        if not self.accounts_file.exists():
            return
        try:
            data = json.loads(self.accounts_file.read_text(encoding="utf-8"))
            for entry in data.get(self.target, []):
                idx = len(self._slots)
                slot = AccountSlot(
                    id=entry.get("id", f"acc_{uuid.uuid4().hex[:8]}"),
                    index=idx,
                    label=entry.get("label", f"account{idx + 1}"),
                    target=self.target,
                    user_data_dir=entry.get("user_data_dir", ""),
                    status="ready",
                    logged_in=entry.get("logged_in", False),
                )
                self._slots.append(slot)
            logger.info("AccountPool[%s]: loaded %d accounts from %s",
                        self.target, len(self._slots), self.accounts_file)
        except Exception as exc:
            logger.warning("AccountPool[%s]: failed to load accounts.json: %s", self.target, exc)

    def _save(self) -> None:
        """Persist current accounts to accounts.json."""
        try:
            # Read existing file to preserve other targets' entries
            if self.accounts_file.exists():
                data = json.loads(self.accounts_file.read_text(encoding="utf-8"))
            else:
                data = {}
            data[self.target] = [s.to_json() for s in self._slots]
            self.accounts_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("AccountPool[%s]: failed to save accounts.json: %s", self.target, exc)

    # ------------------------------------------------------------------ provider init

    async def _ensure_provider(self, slot: AccountSlot) -> None:
        """Lazily initialise the browser provider for a slot."""
        if slot.provider is not None:
            return
        from aeep.providers.browser.browser_provider import BrowserProvider
        from aeep.providers.browser.session import BrowserConfig

        config = BrowserConfig(
            headless=False,
            user_data_dir=slot.user_data_dir,
        )
        provider = BrowserProvider(
            target=slot.target,
            config=config,
            name=f"{slot.target}_{slot.index}",
        )
        await provider._ensure_initialized()
        slot.provider = provider

    # ------------------------------------------------------------------ public API

    def slot_count(self) -> int:
        return len(self._slots)

    def slots(self) -> list[AccountSlot]:
        return list(self._slots)

    async def add_slot(self, label: str | None = None) -> AccountSlot:
        """Add a new account, open browser for login, save to accounts.json."""
        idx = len(self._slots)
        acc_id = f"acc_{uuid.uuid4().hex[:8]}"
        lbl = label.strip() if label and label.strip() else f"account{idx + 1}"

        # Each account gets its own persistent Chrome profile directory
        profile_base = _DEFAULT_PROFILE_BASE / acc_id
        profile_base.mkdir(parents=True, exist_ok=True)
        user_data_dir = str(profile_base)

        slot = AccountSlot(
            id=acc_id,
            index=idx,
            label=lbl,
            target=self.target,
            user_data_dir=user_data_dir,
            status="ready",
        )
        self._slots.append(slot)
        self._save()   # persist before opening browser

        # Open browser and navigate to login page
        await self._ensure_provider(slot)
        page = await slot.provider._session.get_page("login")
        try:
            await page.goto(
                slot.provider._target.base_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await page.bring_to_front()
        except Exception as exc:
            logger.warning("AccountPool: navigate failed: %s", exc)

        logger.info("AccountPool[%s]: added '%s' (id=%s)", self.target, lbl, acc_id)
        return slot

    async def remove_slot(self, index: int) -> None:
        slot = self._slots[index]
        if slot.provider:
            try:
                await slot.provider.close()
            except Exception:
                pass
        self._slots.pop(index)
        for i, s in enumerate(self._slots):
            s.index = i
        self._current_index = min(self._current_index, max(0, len(self._slots) - 1))
        self._save()
        logger.info("AccountPool[%s]: removed '%s'", self.target, slot.label)

    async def complete(
        self,
        messages: Any,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: object,
    ) -> Any:
        """Round-robin completion with automatic rotation on rate limit."""
        if not self._slots:
            raise RuntimeError("No accounts in pool — add one in the Account Management tab.")

        tried = 0
        while tried < len(self._slots):
            slot = self._slots[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._slots)
            tried += 1

            if not slot.is_ready:
                continue

            try:
                await self._ensure_provider(slot)
                logger.info("AccountPool[%s]: using '%s'", self.target, slot.label)
                return await slot.provider.complete(
                    messages, model=model, temperature=temperature,
                    max_tokens=max_tokens, **kwargs,
                )
            except ProviderRateLimitError as exc:
                slot.mark_rate_limited(exc.retry_after or 3600)

        ready_times = [s.cooldown_until for s in self._slots if s.cooldown_until > 0]
        min_ready = min(ready_times) if ready_times else time.time() + 3600
        raise AllAccountsCoolingError(min_ready)

    def status_table(self) -> list[dict]:
        return [s.to_dict() for s in self._slots]
