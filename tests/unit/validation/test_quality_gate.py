"""Tests for QualityGate evaluation."""

from __future__ import annotations

import pytest

from aeep.validation.models import (
    DimensionScore,
    GateDecision,
    Severity,
    ValidationIssue,
    ValidationResult,
)
from aeep.validation.quality_gate import GateRule, QualityGate


def _result(score: float, errors: int = 0, dimensions: dict | None = None) -> ValidationResult:
    dims = [
        DimensionScore(name=k, score=v)
        for k, v in (dimensions or {}).items()
    ]
    issues = [
        ValidationIssue(Severity.ERROR, f"error {i}") for i in range(errors)
    ]
    return ValidationResult(
        artifact_id="test",
        score=score,
        dimensions=dims,
        issues=issues,
    )


class TestQualityGate:
    def test_pass_when_above_hard_gate(self):
        gate = QualityGate(
            name="test",
            hard_gates=[GateRule("hard", min_score=70.0)],
        )
        assert gate.evaluate(_result(85.0)) == GateDecision.PASS

    def test_block_below_hard_gate(self):
        gate = QualityGate(
            name="test",
            hard_gates=[GateRule("hard", min_score=70.0)],
        )
        assert gate.evaluate(_result(60.0)) == GateDecision.BLOCK

    def test_warn_when_below_soft_gate(self):
        gate = QualityGate(
            name="test",
            hard_gates=[GateRule("hard", min_score=50.0)],
            soft_gates=[GateRule("soft", min_score=80.0)],
        )
        assert gate.evaluate(_result(65.0)) == GateDecision.WARN

    def test_block_on_too_many_errors(self):
        gate = QualityGate(
            name="test",
            hard_gates=[GateRule("hard", min_score=0.0, max_error_count=0)],
        )
        assert gate.evaluate(_result(90.0, errors=1)) == GateDecision.BLOCK

    def test_dimension_score_requirement(self):
        gate = QualityGate(
            name="test",
            hard_gates=[GateRule("hard", min_score=0.0,
                                  required_dimensions={"accuracy": 70.0})],
        )
        # accuracy = 60 < 70 → BLOCK
        assert gate.evaluate(_result(90.0, dimensions={"accuracy": 60.0})) == GateDecision.BLOCK
        # accuracy = 80 ≥ 70 → PASS
        assert gate.evaluate(_result(90.0, dimensions={"accuracy": 80.0})) == GateDecision.PASS

    def test_from_dict(self):
        cfg = {
            "hard": {"min_score": 75, "required_dimensions": {"completeness": 70}},
            "soft": {"target_score": 90},
        }
        gate = QualityGate.from_dict("book_chapter", cfg)
        assert gate.name == "book_chapter"
        assert gate.hard_gates[0].min_score == 75.0
        assert gate.hard_gates[0].required_dimensions["completeness"] == 70.0
        assert gate.soft_gates[0].min_score == 90.0

    def test_no_gates_always_pass(self):
        gate = QualityGate(name="empty")
        assert gate.evaluate(_result(0.0, errors=99)) == GateDecision.PASS
