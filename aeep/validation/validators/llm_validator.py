"""LLM validator — multi-dimensional scoring via language model judge."""

from __future__ import annotations

import json
import re
from typing import Any, TYPE_CHECKING

from aeep.validation.models import (
    DimensionScore,
    Severity,
    ValidationIssue,
    ValidationRule,
)

if TYPE_CHECKING:
    from aeep.core.interfaces.provider import LLMProvider

_DEFAULT_DIMENSIONS = [
    "factual_accuracy",
    "completeness",
    "clarity",
    "practicality",
    "innovation",
]

_JUDGE_PROMPT = """\
You are an objective content quality judge.

Evaluate the following content and return a JSON object with scores (0-100) for each dimension.

Dimensions to evaluate:
{dimensions}

Content to evaluate:
\"\"\"
{content}
\"\"\"

Respond ONLY with a JSON object. Example:
{{"factual_accuracy": 85, "completeness": 72, "clarity": 90, "practicality": 78, "innovation": 65}}
"""


class LLMValidator:
    """Uses an LLM to score content across multiple dimensions.

    Calls the LLM ``num_samples`` times and averages the scores to reduce variance.
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str = "gpt-4o-mini",
        num_samples: int = 3,
    ) -> None:
        self._provider = provider
        self._model = model
        self._num_samples = num_samples

    async def validate(self, content: str, rule: ValidationRule) -> DimensionScore:
        cfg = rule.config
        dimensions = cfg.get("dimensions", _DEFAULT_DIMENSIONS)
        num_samples = int(cfg.get("num_samples", self._num_samples))

        all_scores: list[dict[str, float]] = []
        for _ in range(num_samples):
            scores = await self._judge(content, dimensions)
            all_scores.append(scores)

        # Average across samples
        averaged: dict[str, float] = {}
        for dim in dimensions:
            vals = [s.get(dim, 50.0) for s in all_scores]
            averaged[dim] = sum(vals) / len(vals)

        overall = sum(averaged.values()) / len(averaged) if averaged else 50.0

        issues: list[ValidationIssue] = []
        min_dim_score = float(cfg.get("min_dimension_score", 0.0))
        for dim, score in averaged.items():
            if score < min_dim_score:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        message=f"Dimension '{dim}' score {score:.1f} < {min_dim_score}",
                        dimension=dim,
                        suggestion=f"Improve {dim.replace('_', ' ')}",
                    )
                )

        return DimensionScore(
            name=rule.name,
            score=round(overall, 1),
            weight=rule.weight,
            issues=issues,
        )

    async def _judge(self, content: str, dimensions: list[str]) -> dict[str, float]:
        from aeep.core.models.message import Message, Role

        prompt = _JUDGE_PROMPT.format(
            dimensions="\n".join(f"- {d}" for d in dimensions),
            content=content[:3000],
        )
        result = await self._provider.complete(
            messages=[Message(role=Role.USER, content=prompt)],
            model=self._model,
            temperature=0.1,
            max_tokens=256,
        )
        return self._parse_scores(result.content, dimensions)

    @staticmethod
    def _parse_scores(response: str, dimensions: list[str]) -> dict[str, float]:
        # Extract JSON from the response
        match = re.search(r"\{[^}]+\}", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return {k: float(v) for k, v in data.items() if k in dimensions}
            except (json.JSONDecodeError, ValueError):
                pass
        # Fallback: extract "key": number pairs
        scores: dict[str, float] = {}
        for dim in dimensions:
            m = re.search(rf'"{dim}"\s*:\s*(\d+(?:\.\d+)?)', response)
            if m:
                scores[dim] = float(m.group(1))
        return scores
