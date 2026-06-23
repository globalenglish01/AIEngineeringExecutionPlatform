"""Validation Engine — routes to validators, aggregates scores, applies Quality Gate."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from aeep.core.models.artifact import Artifact
from aeep.validation.models import (
    DimensionScore,
    GateDecision,
    RuleType,
    ValidationResult,
    ValidationRule,
)

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider


class ValidationEngine:
    """Central orchestrator for all validation workflows."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider
        self._schema_validator = None
        self._rule_validator = None
        self._llm_validator = None
        self._code_validator = None
        self._consistency_validator = None

    def _get_schema_validator(self):
        if self._schema_validator is None:
            from aeep.validation.validators.schema_validator import SchemaValidator
            self._schema_validator = SchemaValidator()
        return self._schema_validator

    def _get_rule_validator(self):
        if self._rule_validator is None:
            from aeep.validation.validators.rule_validator import RuleValidator
            self._rule_validator = RuleValidator()
        return self._rule_validator

    def _get_llm_validator(self):
        if self._llm_validator is None:
            if self._llm_provider is None:
                raise ValueError("LLM provider required for LLM validation")
            from aeep.validation.validators.llm_validator import LLMValidator
            self._llm_validator = LLMValidator(self._llm_provider)
        return self._llm_validator

    def _get_code_validator(self):
        if self._code_validator is None:
            from aeep.validation.validators.code_validator import CodeValidator
            self._code_validator = CodeValidator()
        return self._code_validator

    def _get_consistency_validator(self):
        if self._consistency_validator is None:
            from aeep.validation.validators.consistency_validator import ConsistencyValidator
            self._consistency_validator = ConsistencyValidator()
        return self._consistency_validator

    async def validate(
        self,
        artifact: Artifact,
        rules: list[ValidationRule],
        context: dict[str, Any] | None = None,
    ) -> ValidationResult:
        content = artifact.content
        dimensions: list[DimensionScore] = []

        for rule in rules:
            dim = await self._dispatch(content, rule)
            dimensions.append(dim)

        # Weighted average score
        total_weight = sum(d.weight for d in dimensions)
        if total_weight > 0:
            score = sum(d.score * d.weight for d in dimensions) / total_weight
        else:
            score = 100.0

        # Flatten issues
        all_issues = [issue for d in dimensions for issue in d.issues]

        result = ValidationResult(
            artifact_id=str(artifact.id),
            score=round(score, 1),
            dimensions=dimensions,
            issues=all_issues,
        )

        # Apply default gate: pass ≥ 70, warn ≥ 50, block otherwise
        if result.error_count > 0 or score < 50.0:
            result.gate_decision = GateDecision.BLOCK
            result.passed = False
        elif score < 70.0:
            result.gate_decision = GateDecision.WARN
            result.passed = True
        else:
            result.gate_decision = GateDecision.PASS
            result.passed = True

        return result

    async def _dispatch(self, content: Any, rule: ValidationRule) -> DimensionScore:
        if rule.rule_type == RuleType.SCHEMA:
            return await self._get_schema_validator().validate(content, rule)
        elif rule.rule_type == RuleType.RULE:
            text = content if isinstance(content, str) else str(content)
            return await self._get_rule_validator().validate(text, rule)
        elif rule.rule_type == RuleType.LLM:
            text = content if isinstance(content, str) else str(content)
            return await self._get_llm_validator().validate(text, rule)
        elif rule.rule_type == RuleType.CODE:
            text = content if isinstance(content, str) else str(content)
            return await self._get_code_validator().validate(text, rule)
        elif rule.rule_type == RuleType.CONSISTENCY:
            text = content if isinstance(content, str) else str(content)
            return await self._get_consistency_validator().validate(text, rule)
        else:
            return DimensionScore(name=rule.name, score=100.0, weight=rule.weight)
