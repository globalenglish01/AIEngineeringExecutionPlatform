"""CustomAPIProvider — any OpenAI-compatible endpoint with user-supplied base_url."""

from __future__ import annotations

from aeep.providers.api.openai_provider import OpenAIProvider


class CustomAPIProvider(OpenAIProvider):
    """For user-defined OpenAI-compatible APIs (local proxies, third-party gateways, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        name: str = "custom",
        display_name: str = "Custom API",
        models: list[str] | None = None,
    ) -> None:
        super().__init__(api_key=api_key, name=name, display_name=display_name, base_url=base_url)
        if models:
            self.supported_models = models
