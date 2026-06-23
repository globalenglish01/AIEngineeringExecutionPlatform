"""ValidationNode — runs validators against an artifact from context."""

from __future__ import annotations

import logging
from typing import Any

from aeep.core.models.artifact import Artifact, ArtifactType
from aeep.core.models.validation import GateResult, QualityGate
from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class ValidationNode(BaseNode):
    """Validates content from context using configured validators.

    Config keys:
        input_key        str   context key holding the text to validate
        artifact_type    str   ArtifactType value (default: "text")
        min_score        float minimum acceptable quality score (default: 70.0)
        gate_type        str   "hard" | "soft" | "progressive" (default: "hard")
        on_fail          str   "raise" | "warn" | "skip" (default: "raise")
        output_key       str   where to store ValidationResult (default: node_id)
    """

    node_type = "validation"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        input_key: str = self.config.get("input_key", "content")
        content: str = context.get(input_key, "")
        artifact_type_str: str = self.config.get("artifact_type", "text")
        min_score: float = float(self.config.get("min_score", 70.0))
        gate_type: str = self.config.get("gate_type", "hard")
        on_fail: str = self.config.get("on_fail", "raise")
        output_key: str = self.config.get("output_key", self.node_id)

        artifact = Artifact(
            artifact_type=ArtifactType(artifact_type_str),
            content=content,
            title=context.get("title", ""),
        )

        gate = QualityGate(
            name=self.node_id,
            min_score=min_score,
            gate_type=gate_type,
            iteration=context.get("_iteration", 1),
        )

        # Run basic heuristic validation (real validators registered in validation engine)
        score = self._heuristic_score(content)
        from aeep.core.models.validation import ValidationResult
        result = ValidationResult(
            validator_name="heuristic",
            passed=score >= min_score,
            score=score,
        )

        gate_result = gate.evaluate(result)
        logger.info(
            "ValidationNode '%s': score=%.1f gate=%s", self.node_id, score, gate_result.value
        )

        if gate_result == GateResult.FAIL and on_fail == "raise":
            from aeep.core.exceptions import QualityGateFailedError
            raise QualityGateFailedError(gate.name, score, gate.effective_min_score())

        return {
            output_key: result,
            f"{self.node_id}_passed": gate_result == GateResult.PASS,
            f"{self.node_id}_score": score,
        }

    @staticmethod
    def _heuristic_score(content: str) -> float:
        """Rough quality score based on length and structure. Real validators plug in here."""
        if not content.strip():
            return 0.0
        word_count = len(content.split())
        score = min(100.0, 50.0 + word_count / 20.0)
        # Penalise very short outputs
        if word_count < 20:
            score = max(0.0, score - 30.0)
        return round(score, 1)
