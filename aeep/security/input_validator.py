"""Input validation and prompt-injection filtering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


# ── Prompt injection patterns ────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    # Classic jailbreak phrases
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?previous\s+instructions?",
    r"you\s+are\s+now\s+(a\s+)?(?:DAN|jailbreak|unrestricted)",
    r"override\s+(your\s+)?system\s+prompt",
    r"disregard\s+(all\s+)?prior\s+(instructions?|context)",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    # Command injection markers inside LLM output
    r"\[\s*system\s*\]",
    r"<\s*\|?\s*im_start\s*\|?\s*>",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE | re.DOTALL
)


def sanitize_llm_output(text: str) -> str:
    """Remove or neutralize prompt-injection patterns from LLM output."""
    return _INJECTION_RE.sub("[REDACTED]", text)


def contains_injection(text: str) -> bool:
    """Return True if the text contains suspected prompt-injection content."""
    return bool(_INJECTION_RE.search(text))


# ── Pydantic-based input validators ─────────────────────────────────────────

class WorkflowInputModel(BaseModel):
    """Validates workflow run inputs."""
    topic: str | None = None
    context: str | None = None
    language: str | None = None
    max_words: int | None = None
    min_score: float | None = None

    model_config = {"extra": "allow"}


class ProviderConfigModel(BaseModel):
    """Validates a provider config dict."""
    name: str
    provider_type: str
    model: str | None = None

    model_config = {"extra": "allow"}


@dataclass
class ValidationResult:
    valid: bool
    value: Any = None
    errors: list[str] | None = None


class InputValidator:
    """Validate and sanitize external inputs using Pydantic schemas."""

    @staticmethod
    def validate_workflow_input(data: dict[str, Any]) -> ValidationResult:
        try:
            model = WorkflowInputModel(**data)
            return ValidationResult(valid=True, value=model.model_dump(exclude_none=True))
        except ValidationError as e:
            return ValidationResult(valid=False, errors=[str(err) for err in e.errors()])

    @staticmethod
    def validate_provider_config(data: dict[str, Any]) -> ValidationResult:
        try:
            model = ProviderConfigModel(**data)
            return ValidationResult(valid=True, value=model.model_dump())
        except ValidationError as e:
            return ValidationResult(valid=False, errors=[str(err) for err in e.errors()])

    @staticmethod
    def sanitize(text: str) -> str:
        return sanitize_llm_output(text)
