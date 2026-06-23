"""Global platform settings  Eloaded from environment variables and YAML."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AEEP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project paths
    project_root: Path = Field(default_factory=Path.cwd)
    config_dir: Path = Field(default=Path("config"))
    secrets_dir: Path = Field(default=Path(".secrets"))
    artifacts_dir: Path = Field(default=Path("artifacts"))
    checkpoints_dir: Path = Field(default=Path(".checkpoints"))

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"   # "json" | "console"

    # Provider defaults
    default_provider: str = "deepseek_api"
    default_model: str = "deepseek-chat"
    default_temperature: float = 0.7
    default_max_tokens: int = 4096

    # Budget controls (USD)
    daily_budget_usd: float | None = None
    monthly_budget_usd: float | None = None

    # Validation
    default_min_quality_score: float = 70.0
    llm_validator_calls: int = 3       # calls per validation
    llm_validator_variance_threshold: float = 15.0  # trigger extra call

    # Timeouts (seconds)
    provider_connect_timeout: int = 10
    provider_read_timeout: int = 120
    browser_page_timeout: int = 120
    browser_login_timeout: int = 300

    # Database
    db_path: Path = Field(default=Path("platform.db"))

    # Encryption (Fernet)
    encryption_key: str | None = Field(default=None, alias="ENCRYPTION_KEY")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")


_settings: PlatformSettings | None = None


def get_settings() -> PlatformSettings:
    global _settings
    if _settings is None:
        _settings = PlatformSettings()
    return _settings


def reset_settings() -> None:
    """For testing only."""
    global _settings
    _settings = None
