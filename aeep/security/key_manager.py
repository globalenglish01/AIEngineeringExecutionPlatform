"""API Key Manager — Fernet-encrypted key storage with env-var fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class APIKeyManager:
    """Manages encrypted API keys on disk with environment variable fallback.

    Key file layout (JSON)::

        {
          "openai": "<fernet-encrypted-base64>",
          "anthropic": "<fernet-encrypted-base64>"
        }

    If the environment variable ``AEEP_<PROVIDER>_API_KEY`` is set, it takes
    precedence over the stored key.
    """

    _ENV_PREFIX = "AEEP_"

    def __init__(
        self,
        key_file: str | Path = ".aeep_keys.enc",
        master_key: bytes | None = None,
    ) -> None:
        self._key_file = Path(key_file)
        # Load or generate master Fernet key
        master_key_path = Path(str(key_file) + ".master")
        if master_key is not None:
            self._fernet = Fernet(master_key)
        elif master_key_path.exists():
            self._fernet = Fernet(master_key_path.read_bytes().strip())
        else:
            new_key = Fernet.generate_key()
            master_key_path.write_bytes(new_key)
            master_key_path.chmod(0o600)
            self._fernet = Fernet(new_key)

        self._store: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._key_file.exists():
            try:
                data = json.loads(self._key_file.read_text())
                self._store = data
            except Exception:
                self._store = {}

    def _save(self) -> None:
        self._key_file.write_text(json.dumps(self._store, indent=2))
        self._key_file.chmod(0o600)

    def set_key(self, provider: str, api_key: str) -> None:
        """Encrypt and persist an API key."""
        encrypted = self._fernet.encrypt(api_key.encode()).decode()
        self._store[provider.lower()] = encrypted
        self._save()

    def get_key(self, provider: str) -> str | None:
        """Retrieve an API key — env var takes precedence."""
        env_name = f"{self._ENV_PREFIX}{provider.upper()}_API_KEY"
        env_val = os.environ.get(env_name)
        if env_val:
            return env_val

        encrypted = self._store.get(provider.lower())
        if not encrypted:
            return None
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            return None

    def delete_key(self, provider: str) -> None:
        self._store.pop(provider.lower(), None)
        self._save()

    def list_providers(self) -> list[str]:
        """List providers that have stored keys."""
        return list(self._store.keys())

    @staticmethod
    def generate_master_key() -> bytes:
        return Fernet.generate_key()
