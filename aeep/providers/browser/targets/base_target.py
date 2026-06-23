"""BaseBrowserTarget — interface that each AI website implementation must satisfy.

⚠️  Playwright imports are allowed in this directory (targets/).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedResponse:
    plain_text: str
    code_blocks: list[dict[str, str]] = field(default_factory=list)  # [{language, code}]

    @property
    def full_markdown(self) -> str:
        """Reconstruct markdown with fenced code blocks."""
        if not self.code_blocks:
            return self.plain_text
        parts = [self.plain_text]
        for block in self.code_blocks:
            lang = block.get("language", "")
            code = block.get("code", "")
            parts.append(f"```{lang}\n{code}\n```")
        return "\n\n".join(parts)


class BaseBrowserTarget(ABC):
    """Abstract interface for a specific AI chat website."""

    target_name: str
    base_url: str

    @abstractmethod
    async def is_logged_in(self, page: Any) -> bool:
        """Return True if the current page shows an authenticated session."""
        ...

    @abstractmethod
    async def send_message(self, page: Any, message: str) -> None:
        """Type and submit *message* in the chat input box."""
        ...

    @abstractmethod
    async def wait_for_response(self, page: Any, timeout_ms: int = 120_000) -> str:
        """Block until the AI finishes generating; return the raw response HTML."""
        ...

    @abstractmethod
    async def extract_response(self, raw_html: str) -> ExtractedResponse:
        """Parse raw_html into structured ExtractedResponse."""
        ...

    async def handle_rate_limit(self, page: Any) -> int:
        """Return the number of seconds to wait when rate-limited. Override per target."""
        return 60

    async def navigate_to_new_chat(self, page: Any) -> None:
        """Open a new conversation (default: reload base_url). Override per target."""
        await page.goto(self.base_url, wait_until="networkidle")
