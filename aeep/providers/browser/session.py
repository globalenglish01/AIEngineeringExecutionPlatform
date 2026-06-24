"""BrowserSession — manages Playwright browser lifecycle with persistent user profile.

Uses launch_persistent_context so each account slot has its own user-data-dir.
This makes the browser indistinguishable from a real Chrome user to Google OAuth.

⚠️  This is the ONLY file (along with targets/*.py and base_browser_provider.py)
    where `import playwright` is allowed. Do not import playwright elsewhere.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import (
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    BrowserContext = Any  # type: ignore[assignment,misc]
    Page = Any  # type: ignore[assignment,misc]
    Playwright = Any  # type: ignore[assignment,misc]

# Anti-detection script injected into every page
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'permissions', {
    get: () => ({ query: () => Promise.resolve({ state: 'granted' }) })
});
"""


class BrowserConfig:
    __slots__ = (
        "browser_type",
        "headless",
        "user_data_dir",   # persistent profile dir — each account gets its own
        "cookie_path",     # legacy; ignored when user_data_dir is set
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
        headless: bool = False,
        user_data_dir: str | None = None,
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
        self.user_data_dir = user_data_dir
        self.cookie_path = cookie_path
        self.login_timeout = login_timeout
        self.max_sessions = max_sessions
        self.idle_timeout = idle_timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.user_agent = user_agent
        self.locale = locale


class BrowserSession:
    """Manages a single Playwright browser context.

    When user_data_dir is set, uses launch_persistent_context (full Chrome
    profile) which passes Google's "secure browser" check.  Falls back to
    the old launch() + new_context() approach when no dir is given.
    """

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright: Any = None
        self._browser: Any = None   # only used in non-persistent mode
        self._context: Any = None
        self._pages: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "playwright is required: uv run python -m playwright install chromium"
            )
        if self._initialized:
            return

        pw_mgr = async_playwright()
        self._playwright = await pw_mgr.__aenter__()
        browser_launcher = getattr(self._playwright, self._config.browser_type)

        # Args that suppress automation detection flags
        stealth_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-extensions-except=",
        ]

        if self._config.user_data_dir:
            # Persistent context — full user profile, passes Google OAuth check
            profile_dir = Path(self._config.user_data_dir)
            profile_dir.mkdir(parents=True, exist_ok=True)

            self._context = await browser_launcher.launch_persistent_context(
                str(profile_dir),
                headless=self._config.headless,
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                user_agent=self._config.user_agent,
                locale=self._config.locale,
                args=stealth_args,
            )
            logger.info("BrowserSession: persistent context at %s", profile_dir)
        else:
            # Legacy: anonymous context (Google may flag this as automated)
            self._browser = await browser_launcher.launch(
                headless=self._config.headless,
                args=stealth_args,
            )
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

        await self._context.add_init_script(_STEALTH_SCRIPT)
        self._initialized = True
        logger.info("BrowserSession initialized (headless=%s)", self._config.headless)

    async def get_page(self, session_id: str = "default") -> Any:
        if session_id in self._pages:
            page = self._pages[session_id]
            if not page.is_closed():
                return page
            del self._pages[session_id]

        if len(self._pages) >= self._config.max_sessions:
            oldest_id = next(iter(self._pages))
            await self._pages[oldest_id].close()
            del self._pages[oldest_id]

        # Reuse existing pages from persistent context if available
        existing = self._context.pages
        if existing and session_id == "default":
            page = existing[0]
        else:
            page = await self._context.new_page()

        self._pages[session_id] = page
        return page

    async def save_cookies(self) -> None:
        """Save storage state (cookies + localStorage) for non-persistent sessions."""
        if not self._config.cookie_path or not self._context:
            return
        if self._config.user_data_dir:
            # Persistent context saves automatically — nothing to do
            logger.info("Persistent context: profile auto-saved at %s", self._config.user_data_dir)
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
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("BrowserSession closed")
