"""DeepSeekTarget — operates chat.deepseek.com via Playwright.

⚠️  Playwright import is allowed here (targets/ directory).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from aeep.core.exceptions import BrowserRateLimitError
from aeep.providers.browser.targets.base_target import BaseBrowserTarget, ExtractedResponse

logger = logging.getLogger(__name__)

_LOGIN_CHECK = "[class*='userAvatar'], [class*='user-avatar'], button[class*='logout']"
_INPUT_BOX = "textarea[placeholder], div[contenteditable='true']"
_SEND_BTN = "button[class*='sendButton'], button[aria-label*='send'], button[aria-label*='Send']"
_LOADING_INDICATOR = (
    "[class*='loading'], [class*='thinking'], [class*='generating'], "
    "[class*='stopButton'], button[class*='stop']"
)
_RESPONSE_CONTAINER = "[class*='assistant']"
_STOP_BTN = "button[class*='stop'], [class*='stopButton']"
_RATE_LIMIT_TEXT = "Too many requests"


class DeepSeekTarget(BaseBrowserTarget):
    target_name = "deepseek"
    base_url = "https://chat.deepseek.com"

    async def is_logged_in(self, page: Any) -> bool:
        try:
            await page.wait_for_selector(_LOGIN_CHECK, timeout=5_000)
            return True
        except Exception:
            return False

    async def navigate_to_new_chat(self, page: Any) -> None:
        await page.goto(self.base_url, wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

    async def send_message(self, page: Any, message: str) -> None:
        await page.wait_for_selector(_INPUT_BOX, timeout=10_000)
        input_el = await page.query_selector(_INPUT_BOX)
        if input_el:
            await input_el.click()
            await input_el.fill("")
            await page.keyboard.type(message, delay=15)
        # Press Enter to send (DeepSeek uses Enter, not a send button in some versions)
        send_els = await page.query_selector_all(_SEND_BTN)
        if send_els:
            await send_els[-1].click()
        else:
            await page.keyboard.press("Enter")
        logger.debug("DeepSeek: message sent (%d chars)", len(message))

    async def wait_for_response(self, page: Any, timeout_ms: int = 120_000) -> str:
        # Wait for generation to start (stop button appears)
        try:
            await page.wait_for_selector(_STOP_BTN, state="visible", timeout=10_000)
        except Exception:
            pass

        # Poll until text stops changing (more reliable than loading indicators)
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        prev_text = ""
        stable_count = 0
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(1.5)
            elements = await page.query_selector_all(_RESPONSE_CONTAINER)
            cur_text = await elements[-1].inner_text() if elements else ""
            if cur_text and cur_text == prev_text:
                stable_count += 1
                if stable_count >= 2:  # stable for 3s → done
                    break
            else:
                stable_count = 0
            prev_text = cur_text

            # Check if stop button is gone (also indicates completion)
            stop_visible = await page.query_selector(_STOP_BTN)
            if not stop_visible and cur_text:
                await asyncio.sleep(0.5)
                break

        await asyncio.sleep(0.3)
        content = await page.content()
        if _RATE_LIMIT_TEXT in content:
            logger.warning("DeepSeek: rate limit detected")
            raise BrowserRateLimitError(retry_after=3600)

        elements = await page.query_selector_all(_RESPONSE_CONTAINER)
        if not elements:
            return ""
        # Use inner_text() — plain text without HTML tags, cleaner for LLM parsing
        return await elements[-1].inner_text()

    async def extract_response(self, raw_text: str) -> ExtractedResponse:
        # wait_for_response now returns inner_text() — already plain text
        text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
        return ExtractedResponse(plain_text=text, code_blocks=[])
