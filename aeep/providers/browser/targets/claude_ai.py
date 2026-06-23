"""ClaudeAITarget — operates claude.ai via Playwright.

⚠️  Playwright import is allowed here (targets/ directory).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from aeep.providers.browser.targets.base_target import BaseBrowserTarget, ExtractedResponse

logger = logging.getLogger(__name__)

_LOGIN_CHECK = "[data-testid='user-menu-trigger'], button[aria-label*='Account']"
_INPUT_BOX = "div[contenteditable='true'][data-placeholder]"
_SEND_BTN = "button[aria-label='Send Message']"
_STREAMING_INDICATOR = "[class*='streaming'], button[aria-label='Stop Response']"
_RESPONSE_CONTAINER = "[data-testid='assistant-message'], [class*='prose']"
_RATE_LIMIT_TEXT = "usage limit"


class ClaudeAITarget(BaseBrowserTarget):
    target_name = "claude_ai"
    base_url = "https://claude.ai"

    async def is_logged_in(self, page: Any) -> bool:
        try:
            await page.wait_for_selector(_LOGIN_CHECK, timeout=5_000)
            return True
        except Exception:
            return False

    async def navigate_to_new_chat(self, page: Any) -> None:
        await page.goto(f"{self.base_url}/new", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

    async def send_message(self, page: Any, message: str) -> None:
        await page.wait_for_selector(_INPUT_BOX, timeout=10_000)
        await page.click(_INPUT_BOX)
        # Claude.ai uses a contenteditable div — type() works correctly
        await page.type(_INPUT_BOX, message, delay=10)
        await page.wait_for_selector(_SEND_BTN, timeout=5_000)
        await page.click(_SEND_BTN)
        logger.debug("Claude.ai: message sent (%d chars)", len(message))

    async def wait_for_response(self, page: Any, timeout_ms: int = 120_000) -> str:
        # Wait for streaming indicator to appear
        try:
            await page.wait_for_selector(_STREAMING_INDICATOR, state="visible", timeout=8_000)
        except Exception:
            pass

        # Wait for streaming to finish
        await page.wait_for_selector(_STREAMING_INDICATOR, state="hidden", timeout=timeout_ms)
        await asyncio.sleep(0.5)

        content = await page.content()
        if _RATE_LIMIT_TEXT in content.lower():
            logger.warning("Claude.ai: usage limit detected")
            return ""

        elements = await page.query_selector_all(_RESPONSE_CONTAINER)
        if not elements:
            return ""
        return await elements[-1].inner_html()

    async def extract_response(self, raw_html: str) -> ExtractedResponse:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(raw_html, "html.parser")
            code_blocks: list[dict[str, str]] = []

            for pre in soup.find_all("pre"):
                code_tag = pre.find("code")
                if code_tag:
                    lang = ""
                    for cls in code_tag.get("class", []):
                        if cls.startswith("language-"):
                            lang = cls.removeprefix("language-")
                    code_blocks.append({"language": lang, "code": code_tag.get_text()})
                    pre.decompose()

            plain_text = soup.get_text(separator="\n").strip()
            plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)
            return ExtractedResponse(plain_text=plain_text, code_blocks=code_blocks)
        except ImportError:
            clean = re.sub(r"<[^>]+>", "", raw_html)
            return ExtractedResponse(plain_text=clean.strip())

    async def handle_rate_limit(self, page: Any) -> int:
        return 3600  # Claude.ai daily limits are long; wait an hour by default
