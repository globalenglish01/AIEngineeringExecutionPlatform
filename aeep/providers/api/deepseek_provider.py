"""DeepSeek Provider — OpenAI-compatible API at api.deepseek.com."""

from __future__ import annotations

from aeep.providers.api.openai_provider import OpenAIProvider

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek uses the OpenAI-compatible REST format; only base_url differs."""

    supported_models = ["deepseek-chat", "deepseek-reasoner"]

    PRICING: dict[str, tuple[float, float]] = {
        "deepseek-chat":     (0.00027, 0.0011),
        "deepseek-reasoner": (0.00055, 0.0022),
    }

    def __init__(
        self,
        api_key: str,
        name: str = "deepseek",
        display_name: str = "DeepSeek (API)",
    ) -> None:
        super().__init__(
            api_key=api_key,
            name=name,
            display_name=display_name,
            base_url=_DEEPSEEK_BASE_URL,
        )

    def _default_model(self) -> str:
        return "deepseek-chat"
