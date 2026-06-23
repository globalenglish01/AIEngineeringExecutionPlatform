"""Benchmark suite — task definitions and YAML loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BenchmarkTask:
    task_id: str
    name: str
    description: str
    input: str
    expected_keywords: list[str] = field(default_factory=list)
    min_score: float = 70.0
    validation_rules: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class BenchmarkSuite:
    suite_id: str
    name: str
    description: str = ""
    tasks: list[BenchmarkTask] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BenchmarkSuite":
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        tasks = [
            BenchmarkTask(
                task_id=t.get("task_id", f"t{i}"),
                name=t.get("name", f"Task {i}"),
                description=t.get("description", ""),
                input=t.get("input", ""),
                expected_keywords=t.get("expected_keywords", []),
                min_score=float(t.get("min_score", 70.0)),
                validation_rules=t.get("validation_rules", []),
                tags=t.get("tags", []),
            )
            for i, t in enumerate(data.get("tasks", []))
        ]
        return cls(
            suite_id=data.get("suite_id", Path(path).stem),
            name=data.get("name", Path(path).stem),
            description=data.get("description", ""),
            tasks=tasks,
            tags=data.get("tags", []),
        )
