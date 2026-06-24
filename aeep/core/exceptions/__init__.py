"""Platform exception hierarchy."""
from __future__ import annotations


class PlatformError(Exception):
    """Base for all platform errors."""


class ProviderError(PlatformError):
    def __init__(self, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] {message}")


class ProviderNotFoundError(PlatformError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Provider not found: '{name}'")


class AllProvidersFailedError(PlatformError):
    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        detail = "; ".join(f"{k}: {v}" for k, v in errors.items())
        super().__init__(f"All providers failed -- {detail}")


class ProviderRateLimitError(ProviderError):
    def __init__(self, provider_name: str, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limited"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(provider_name, msg)


class CircuitBreakerOpenError(ProviderError):
    pass


class BrowserInitError(PlatformError):
    pass


class BrowserLoginError(PlatformError):
    pass


class BrowserSessionError(PlatformError):
    pass


class BrowserRateLimitError(BrowserSessionError):
    """Raised by a browser target when the site enforces a usage limit."""

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")


class ValidationError(PlatformError):
    pass


class QualityGateFailedError(PlatformError):
    def __init__(self, gate_name: str, score: float, min_score: float) -> None:
        super().__init__(
            f"Quality gate '{gate_name}' failed: score {score:.1f} < {min_score:.1f}"
        )


class ConfigError(PlatformError):
    pass


class SecretNotFoundError(ConfigError):
    def __init__(self, key_name: str) -> None:
        super().__init__(f"Secret not found: '{key_name}'")


__all__ = [
    "AllProvidersFailedError",
    "BrowserInitError",
    "BrowserLoginError",
    "BrowserRateLimitError",
    "BrowserSessionError",
    "CircuitBreakerOpenError",
    "ConfigError",
    "PlatformError",
    "ProviderError",
    "ProviderNotFoundError",
    "ProviderRateLimitError",
    "QualityGateFailedError",
    "SecretNotFoundError",
    "ValidationError",
]
