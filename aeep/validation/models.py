"""Validation domain models — rules, results, and gate decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuleType(str, Enum):
    SCHEMA = "schema"
    RULE = "rule"
    LLM = "llm"
    CODE = "code"
    CONSISTENCY = "consistency"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GateDecision(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class ValidationRule:
    name: str
    rule_type: RuleType
    weight: float = 1.0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationIssue:
    severity: Severity
    message: str
    dimension: str = ""
    suggestion: str = ""


@dataclass
class DimensionScore:
    name: str
    score: float          # 0–100
    weight: float = 1.0
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class ValidationResult:
    artifact_id: str = ""
    score: float = 0.0
    dimensions: list[DimensionScore] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    passed: bool = False
    gate_decision: GateDecision = GateDecision.BLOCK
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)
