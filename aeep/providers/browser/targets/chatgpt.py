"""ChatGPTTarget — operates chat.openai.com via Playwright.

⚠️  Playwright import is allowed here (targets/ directory).
DOM selectors are accurate as of mid-2026; update when the UI changes.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from aeep.providers.browser.targets.base_target import BaseBrowserTarget, ExtractedResponse

logger = logging.getLogger(__name__)

# Selectors — update when OpenAI changes their DOM
_LOGIN_CHECK = "[data-testid='profile-button'], nav[aria-label='Chat history']"
_INPUT_BOX = "#prompt-textarea"
_SEND_BTN = "[data-testid='send-button']"
_STOP_BTN = "[data-testid='stop-button']"
_RESPONSE_CONTAINER = "[data-message-author-role='assistant']"
_RATE_LIMIT_TEXT = "You've reached our limit"


class ChatGPTTarget(BaseBrowserTarget):
    target_name = "chatgpt"
    base_url = "https://chat.openai.com"

    async def is_logged_in(self, page: Any) -> bool:
        try:
            await page.wait_for_selector(_LOGIN_CHECK, timeout=5_000)
            return True
        except Exception:
            return False

    async def navigate_to_new_chat(self, page: Any) -> None:
        await page.goto(self.base_url, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

    async def send_message(self, page: Any, message: str) -> None:
        await page.wait_for_selector(_INPUT_BOX, timeout=10_000)
        await page.click(_INPUT_BOX)
        await page.fill(_INPUT_BOX, "")
        # Type in chunks to stay within the input box limits
        chunk_size = 20_000
        for i in range(0, len(message), chunk_size):
            await page.type(_INPUT_BOX, message[i : i + chunk_size], delay=20)
            await asyncio.sleep(0.1)
        # Wait for send button to become enabled
        await page.wait_for_selector(_SEND_BTN, timeout=5_000)
        await page.click(_SEND_BTN)
        logger.debug("ChatGPT: message sent (%d chars)", len(message))

    async def wait_for_response(self, page: Any, timeout_ms: int = 120_000) -> str:
        # Wait for stop button to appear (generation started)
        try:
            await page.wait_for_selector(_STOP_BTN, state="visible", timeout=10_000)
        except Exception:
            pass  # may have been too fast

        # Wait for stop button to disappear (generation finished)
        await page.wait_for_selector(_STOP_BTN, state="hidden", timeout=timeout_ms)

        # Check for rate limit message
        content = await page.content()
        if _RATE_LIMIT_TEXT in content:
            logger.warning("ChatGPT: rate limit detected")
            return ""

        # Grab the last assistant message
        elements = await page.query_selector_all(_RESPONSE_CONTAINER)
        if not elements:
            return ""
        return await elements[-1].inner_html()

    async def extract_response(self, raw_html: str) -> ExtractedResponse:
        """Parse ChatGPT response HTML into plain text + code blocks."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(raw_html, "html.parser")
            code_blocks: list[dict[str, str]] = []

            for pre in soup.find_all("pre"):
                code_tag = pre.find("code")
                if code_tag:
                    lang = ""
                    classes = code_tag.get("class", [])
                    for cls in classes:
                        if cls.startswith("language-"):
                            lang = cls.removeprefix("language-")
                    code_blocks.append({"language": lang, "code": code_tag.get_text()})
                    pre.decompose()  # remove from tree so it doesn't appear in plain text

            plain_text = soup.get_text(separator="\n").strip()
            plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)

            return ExtractedResponse(plain_text=plain_text, code_blocks=code_blocks)
        except ImportError:
            # beautifulsoup4 not installed; return raw text stripped of HTML tags
            clean = re.sub(r"<[^>]+>", "", raw_html)
            return ExtractedResponse(plain_text=clean.strip())

    async def handle_rate_limit(self, page: Any) -> int:
        # Try to parse "Please wait X minutes" from page
        try:
            text = await page.inner_text("body")
            match = re.search(r"(\d+)\s*minute", text, re.IGNORECASE)
            if match:
                return int(match.group(1)) * 60
        except Exception:
            pass
        return 60
