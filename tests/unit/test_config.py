"""Tests for the configuration system."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from aeep.config.provider_config import ProviderConfig, load_providers_config
from aeep.config.settings import PlatformSettings, get_settings, reset_settings


@pytest.fixture(autouse=True)
def clean_settings():
    reset_settings()
    yield
    reset_settings()


class TestPlatformSettings:
    def test_defaults(self):
        s = PlatformSettings()
        assert s.log_level == "INFO"
        assert s.default_temperature == 0.7
        assert s.llm_validator_calls == 3

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("AEEP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("AEEP_DEFAULT_MAX_TOKENS", "8192")
        s = PlatformSettings()
        assert s.log_level == "DEBUG"
        assert s.default_max_tokens == 8192

    def test_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestLoadProvidersConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        cfg = load_providers_config(tmp_path / "nonexistent.yaml")
        assert cfg.providers == {}

    def test_load_api_provider(self, tmp_path):
        yaml_content = textwrap.dedent("""
            providers:
              openai_gpt4o:
                type: api
                class: OpenAIProvider
                display_name: "OpenAI GPT-4o"
                models:
                  - gpt-4o
                  - gpt-4o-mini
                auth:
                  key_env: OPENAI_API_KEY
        """)
        f = tmp_path / "providers.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        cfg = load_providers_config(f)

        assert "openai_gpt4o" in cfg.providers
        p = cfg.providers["openai_gpt4o"]
        assert p.type == "api"
        assert "gpt-4o" in p.models
        assert p.auth.key_env == "OPENAI_API_KEY"

    def test_load_browser_provider(self, tmp_path):
        yaml_content = textwrap.dedent("""
            providers:
              chatgpt_browser:
                type: browser
                target: chatgpt
                browser: chromium
                headless: true
                auth:
                  method: cookie_file
                  cookie_path: .secrets/chatgpt_cookies.json
                fallback: deepseek_api
        """)
        f = tmp_path / "providers.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        cfg = load_providers_config(f)

        p = cfg.providers["chatgpt_browser"]
        assert p.type == "browser"
        assert p.target == "chatgpt"
        assert p.fallback == "deepseek_api"
        assert p.auth.cookie_path == ".secrets/chatgpt_cookies.json"

    def test_load_circuit_breaker_config(self, tmp_path):
        yaml_content = textwrap.dedent("""
            circuit_breaker:
              enabled: true
              failure_threshold: 5
              recovery_timeout: 90
        """)
        f = tmp_path / "providers.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        cfg = load_providers_config(f)
        assert cfg.circuit_breaker.failure_threshold == 5
        assert cfg.circuit_breaker.recovery_timeout == 90

    def test_load_fallback_chains(self, tmp_path):
        yaml_content = textwrap.dedent("""
            fallback_chains:
              default:
                - deepseek_api
                - openai_gpt4o
                - ollama_llama3
        """)
        f = tmp_path / "providers.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        cfg = load_providers_config(f)
        assert cfg.fallback_chains["default"] == [
            "deepseek_api",
            "openai_gpt4o",
            "ollama_llama3",
        ]
