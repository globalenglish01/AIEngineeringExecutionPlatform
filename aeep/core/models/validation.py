"""Validation result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"    # blocks quality gate
    WARNING = "warning"
    INFO = "info"


class GateResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # gate not applicable for this artifact


@dataclass
class ValidationIssue:
    severity: Severity
    message: str
    validator_name: str
    field: str | None = None  # which field triggered the issue
    suggestion: str | None = None


@dataclass
class ValidationResult:
    validator_name: str
    passed: bool
    score: float  # 0.0 – 100.0
    issues: list[ValidationIssue] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)


@dataclass
class QualityGate:
    name: str
    min_score: float           # hard threshold
    max_error_count: int = 0   # any error → fail by default
    gate_type: str = "hard"    # "hard" | "soft" | "progressive"
    # progressive gate parameters
    iteration: int = 1
    base_score: float = 60.0
    target_score: float = 85.0
    increment_per_iter: float = 5.0

    def effective_min_score(self) -> float:
        if self.gate_type != "progressive":
            return self.min_score
        score = self.base_score + (self.iteration - 1) * self.increment_per_iter
        return min(score, self.target_score)

    def evaluate(self, result: ValidationResult) -> GateResult:
        if result.error_count > self.max_error_count:
            return GateResult.FAIL
        if result.score < self.effective_min_score():
            return GateResult.FAIL
        return GateResult.PASS
