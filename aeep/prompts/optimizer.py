"""Simple A/B prompt optimizer based on historical scores."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from aeep.prompts.template import PromptTemplate


@dataclass
class TemplateScore:
    template: PromptTemplate
    scores: list[float] = field(default_factory=list)

    @property
    def mean_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0


class PromptOptimizer:
    """Tracks quality scores per template version and selects best for A/B tests."""

    def __init__(self) -> None:
        self._scores: dict[str, list[TemplateScore]] = {}

    def register(self, template: PromptTemplate) -> None:
        ts = TemplateScore(template=template)
        self._scores.setdefault(template.name, []).append(ts)

    def record_score(self, name: str, version: int, score: float) -> None:
        for ts in self._scores.get(name, []):
            if ts.template.version == version:
                ts.scores.append(score)
                return

    def best(self, name: str) -> PromptTemplate | None:
        candidates = self._scores.get(name, [])
        if not candidates:
            return None
        return max(candidates, key=lambda ts: ts.mean_score).template

    def ab_select(self, name: str) -> PromptTemplate | None:
        """Epsilon-greedy: 80% best, 20% random exploration."""
        candidates = self._scores.get(name, [])
        if not candidates:
            return None
        if random.random() < 0.8:
            return self.best(name)
        return random.choice(candidates).template