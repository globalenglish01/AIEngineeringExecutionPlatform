"""Quality Gate — hard/soft gate evaluation with YAML config support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aeep.validation.models import GateDecision, ValidationResult


@dataclass
class GateRule:
    name: str
    min_score: float = 0.0
    required_dimensions: dict[str, float] = field(default_factory=dict)
    max_error_count: int = 999


@dataclass
class QualityGate:
    """Evaluates a ValidationResult against hard and soft gates.

    Hard gates that fail → BLOCK.
    Soft gates that fail → WARN.
    All pass → PASS.
    """

    name: str = "default"
    hard_gates: list[GateRule] = field(default_factory=list)
    soft_gates: list[GateRule] = field(default_factory=list)

    def evaluate(self, result: ValidationResult) -> GateDecision:
        # Check hard gates
        for gate in self.hard_gates:
            if not self._gate_passes(result, gate):
                return GateDecision.BLOCK

        # Check soft gates
        for gate in self.soft_gates:
            if not self._gate_passes(result, gate):
                return GateDecision.WARN

        return GateDecision.PASS

    def _gate_passes(self, result: ValidationResult, gate: GateRule) -> bool:
        if result.error_count > gate.max_error_count:
            return False
        if result.score < gate.min_score:
            return False
        # Check per-dimension minimums
        dim_scores = {d.name: d.score for d in result.dimensions}
        for dim_name, min_score in gate.required_dimensions.items():
            if dim_scores.get(dim_name, 0.0) < min_score:
                return False
        return True

    @classmethod
    def from_dict(cls, name: str, cfg: dict[str, Any]) -> "QualityGate":
        hard_cfg = cfg.get("hard", {})
        soft_cfg = cfg.get("soft", {})

        hard_gate = GateRule(
            name=f"{name}_hard",
            min_score=float(hard_cfg.get("min_score", 0.0)),
            required_dimensions={
                k: float(v)
                for k, v in hard_cfg.get("required_dimensions", {}).items()
            },
            max_error_count=int(hard_cfg.get("max_error_count", 999)),
        )
        soft_gate = GateRule(
            name=f"{name}_soft",
            min_score=float(soft_cfg.get("target_score", 0.0)),
            required_dimensions={
                k: float(v)
                for k, v in soft_cfg.get("recommended_dimensions", {}).items()
            },
        )
        return cls(
            name=name,
            hard_gates=[hard_gate],
            soft_gates=[soft_gate],
        )

    @classmethod
    def load_from_yaml(cls, path: str | Path, gate_name: str) -> "QualityGate":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        gates = data.get("quality_gates", {})
        if gate_name not in gates:
            raise KeyError(f"Gate {gate_name!r} not found in {path}")
        return cls.from_dict(gate_name, gates[gate_name])
