"""DeepSeekTarget — operates chat.deepseek.com via Playwright.

⚠️  Playwright import is allowed here (targets/ directory).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from aeep.providers.browser.targets.base_target import BaseBrowserTarget, ExtractedResponse

logger = logging.getLogger(__name__)

_LOGIN_CHECK = "[class*='userAvatar'], [class*='user-avatar'], button[class*='logout']"
_INPUT_BOX = "textarea[placeholder], div[contenteditable='true']"
_SEND_BTN = "button[class*='sendButton'], button[aria-label*='send'], button[aria-label*='Send']"
_LOADING_INDICATOR = "[class*='loading'], [class*='thinking'], [class*='generating']"
_RESPONSE_CONTAINER = "[class*='markdown'], [class*='ds-markdown'], [class*='chat-message']"
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
        # Wait for loading indicator to appear
        try:
            await page.wait_for_selector(_LOADING_INDICATOR, state="visible", timeout=8_000)
        except Exception:
            pass

        # Wait for loading indicator to disappear (response complete)
        await page.wait_for_selector(_LOADING_INDICATOR, state="hidden", timeout=timeout_ms)
        await asyncio.sleep(0.5)  # brief settle time

        content = await page.content()
        if _RATE_LIMIT_TEXT in content:
            logger.warning("DeepSeek: rate limit detected")
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

            for code_div in soup.find_all("div", class_=re.compile(r"md-code|code-block")):
                lang_tag = code_div.find(class_=re.compile(r"lang|language"))
                lang = lang_tag.get_text().strip() if lang_tag else ""
                code_el = code_div.find("code")
                if code_el:
                    code_blocks.append({"language": lang, "code": code_el.get_text()})
                code_div.decompose()

            plain_text = soup.get_text(separator="\n").strip()
            plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)
            return ExtractedResponse(plain_text=plain_text, code_blocks=code_blocks)
        except ImportError:
            clean = re.sub(r"<[^>]+>", "", raw_html)
            return ExtractedResponse(plain_text=clean.strip())
