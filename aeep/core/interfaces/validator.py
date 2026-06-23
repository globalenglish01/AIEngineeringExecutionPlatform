"""Validator interface."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from aeep.core.models.artifact import Artifact
from aeep.core.models.validation import ValidationResult


class ValidatorType(str, Enum):
    SCHEMA = "schema"
    RULE = "rule"
    LLM = "llm"
    CODE = "code"
    HUMAN_REVIEW = "human_review"
    CONSISTENCY = "consistency"


@runtime_checkable
class Validator(Protocol):
    name: str
    validator_type: ValidatorType
    # weight when aggregating scores from multiple validators (0.0  E1.0)
    weight: float

    async def validate(self, artifact: Artifact) -> ValidationResult: ...

    def supports(self, artifact_type: str) -> bool:
        """Return True if this validator can handle the given artifact type."""
        ...
