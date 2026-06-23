"""Provider configuration models and YAML loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    key_env: str | None = None       # environment variable name
    key_name: str | None = None      # SecretManager key name
    method: str | None = None        # for browser: "cookie_file"
    cookie_path: str | None = None


class RetryConfig(BaseModel):
    max_attempts: int = 3
    delay_seconds: float = 3.0
    backoff_factor: float = 2.0


class SessionConfig(BaseModel):
    reuse: bool = True
    max_sessions: int = 2
    idle_timeout: int = 1800


class StealthConfig(BaseModel):
    enabled: bool = True
    random_delay: bool = True


class RateLimitConfig(BaseModel):
    cooldown_seconds: int = 60
    auto_fallback_after: int = 2


class ProviderConfig(BaseModel):
    type: Literal["api", "local", "browser"]
    class_name: str = Field(alias="class", default="")
    display_name: str = ""
    models: list[str] = Field(default_factory=list)
    default_model: str = ""
    base_url: str | None = None
    auth: AuthConfig = Field(default_factory=AuthConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    fallback: str | None = None
    # browser-specific
    target: str | None = None
    browser: str = "chromium"
    headless: bool = True
    session: SessionConfig = Field(default_factory=SessionConfig)
    stealth: StealthConfig = Field(default_factory=StealthConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    model_config = {"populate_by_name": True}


class CircuitBreakerConfig(BaseModel):
    enabled: bool = True
    failure_threshold: int = 3
    recovery_timeout: int = 60
    success_threshold: int = 1
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class BudgetConfig(BaseModel):
    daily_limit_usd: float | None = None
    monthly_limit_usd: float | None = None
    warning_threshold: float = 0.80


class ProvidersFileConfig(BaseModel):
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    fallback_chains: dict[str, list[str]] = Field(default_factory=dict)


def load_providers_config(path: str | Path = "config/providers.yaml") -> ProvidersFileConfig:
    p = Path(path)
    if not p.exists():
        return ProvidersFileConfig()
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return ProvidersFileConfig.model_validate(raw)
