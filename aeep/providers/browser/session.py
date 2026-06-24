"""BrowserSession — manages Playwright browser lifecycle and cookie persistence.

⚠️  This is the ONLY file (along with targets/*.py and base_browser_provider.py)
    where `import playwright` is allowed. Do not import playwright elsewhere.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    # Type stubs so the rest of the file still type-checks without playwright installed
    Browser = Any  # type: ignore[assignment,misc]
    BrowserContext = Any  # type: ignore[assignment,misc]
    Page = Any  # type: ignore[assignment,misc]
    Playwright = Any  # type: ignore[assignment,misc]


class BrowserConfig:
    __slots__ = (
        "browser_type",
        "headless",
        "cookie_path",
        "login_timeout",
        "max_sessions",
        "idle_timeout",
        "viewport_width",
        "viewport_height",
        "user_agent",
        "locale",
    )

    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = False,          # False = visible window; user can do Google login manually
        cookie_path: str | None = None,
        login_timeout: int = 300,
        max_sessions: int = 3,
        idle_timeout: int = 1800,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale: str = "en-US",
    ) -> None:
        self.browser_type = browser_type
        self.headless = headless
        self.cookie_path = cookie_path
        self.login_timeout = login_timeout
        self.max_sessions = max_sessions
        self.idle_timeout = idle_timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.user_agent = user_agent
        self.locale = locale


class BrowserSession:
    """Manages a single Playwright browser context with cookie persistence."""

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: dict[str, Any] = {}  # session_id → Page
        self._initialized = False

    async def initialize(self) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "playwright is required for Browser Provider: "
                "uv add 'aeep[browser]' && playwright install chromium"
            )
        if self._initialized:
            return

        pw_mgr = async_playwright()
        self._playwright = await pw_mgr.__aenter__()

        browser_launcher = getattr(self._playwright, self._config.browser_type)
        self._browser = await browser_launcher.launch(headless=self._config.headless)

        context_opts: dict[str, Any] = {
            "viewport": {
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
            "user_agent": self._config.user_agent,
            "locale": self._config.locale,
        }

        if self._config.cookie_path and Path(self._config.cookie_path).exists():
            context_opts["storage_state"] = self._config.cookie_path
            logger.info("Loaded cookies from %s", self._config.cookie_path)

        self._context = await self._browser.new_context(**context_opts)

        # Inject anti-detection script on every page
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        self._initialized = True
        logger.info("BrowserSession initialized (headless=%s)", self._config.headless)

    async def get_page(self, session_id: str = "default") -> Any:
        """Return existing page or create a new one (respects max_sessions)."""
        if session_id in self._pages:
            page = self._pages[session_id]
            if not page.is_closed():
                return page
            del self._pages[session_id]

        if len(self._pages) >= self._config.max_sessions:
            # Close the oldest session to make room
            oldest_id = next(iter(self._pages))
            await self._pages[oldest_id].close()
            del self._pages[oldest_id]
            logger.warning("Session pool full — evicted session '%s'", oldest_id)

        page = await self._context.new_page()
        self._pages[session_id] = page
        logger.debug("Created new browser page for session '%s'", session_id)
        return page

    async def save_cookies(self) -> None:
        if not self._config.cookie_path or not self._context:
            return
        path = Path(self._config.cookie_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(path))
        logger.info("Cookies saved to %s", path)

    async def close(self) -> None:
        for page in list(self._pages.values()):
            try:
                await page.close()
            except Exception:
                pass
        self._pages.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("BrowserSession closed")
