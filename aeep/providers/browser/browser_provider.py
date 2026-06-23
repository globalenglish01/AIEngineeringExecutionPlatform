"""BrowserProvider — unified entry point that routes to the configured target.

⚠️  Playwright imports are allowed in this directory.
"""

from __future__ import annotations

from aeep.providers.browser.base_browser_provider import BaseBrowserProvider
from aeep.providers.browser.session import BrowserConfig
from aeep.providers.browser.targets.base_target import BaseBrowserTarget
from aeep.providers.browser.targets.chatgpt import ChatGPTTarget
from aeep.providers.browser.targets.claude_ai import ClaudeAITarget
from aeep.providers.browser.targets.deepseek import DeepSeekTarget

_TARGET_REGISTRY: dict[str, type[BaseBrowserTarget]] = {
    "chatgpt": ChatGPTTarget,
    "deepseek": DeepSeekTarget,
    "claude_ai": ClaudeAITarget,
}


class BrowserProvider(BaseBrowserProvider):
    """Factory-style provider: instantiate by passing a target name string."""

    def __init__(
        self,
        target: str,
        config: BrowserConfig | None = None,
        name: str | None = None,
        display_name: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        if target not in _TARGET_REGISTRY:
            available = ", ".join(_TARGET_REGISTRY)
            raise ValueError(f"Unknown browser target '{target}'. Available: {available}")

        target_cls = _TARGET_REGISTRY[target]
        target_instance = target_cls()
        _config = config or BrowserConfig()
        _name = name or f"browser_{target}"
        _display = display_name or f"{target.replace('_', ' ').title()} (Browser)"

        super().__init__(
            target=target_instance,
            config=_config,
            name=_name,
            display_name=_display,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    @classmethod
    def register_target(cls, name: str, target_cls: type[BaseBrowserTarget]) -> None:
        """Allow third-party targets to be registered at runtime."""
        _TARGET_REGISTRY[name] = target_cls
