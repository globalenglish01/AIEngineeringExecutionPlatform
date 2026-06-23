"""In-process metrics collection (no external dependency).

Provides counters and histograms that can be scraped or logged.
Use ``get_metrics()`` to access the singleton.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class Counter:
    name: str
    labels: dict[str, str]
    _value: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        return self._value


@dataclass
class Histogram:
    name: str
    labels: dict[str, str]
    _samples: list[float] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def observe(self, value: float) -> None:
        with self._lock:
            self._samples.append(value)

    @property
    def count(self) -> int:
        return len(self._samples)

    @property
    def sum(self) -> float:
        return sum(self._samples)

    @property
    def mean(self) -> float:
        return self.sum / self.count if self.count else 0.0


class MetricsRegistry:
    """Thread-safe in-process metrics store."""

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = Lock()

    def _label_key(self, name: str, labels: dict[str, str]) -> str:
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def counter(self, name: str, labels: dict[str, str] | None = None) -> Counter:
        key = self._label_key(name, labels or {})
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(name=name, labels=labels or {})
            return self._counters[key]

    def histogram(self, name: str, labels: dict[str, str] | None = None) -> Histogram:
        key = self._label_key(name, labels or {})
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = Histogram(name=name, labels=labels or {})
            return self._histograms[key]

    # ── Convenience recorders ────────────────────────────────────────────────

    def record_workflow_run(self, workflow_name: str, duration_s: float, success: bool) -> None:
        self.counter("workflow_run_total",
                     {"workflow": workflow_name, "status": "success" if success else "failure"}).inc()
        self.histogram("workflow_run_duration_seconds", {"workflow": workflow_name}).observe(duration_s)

    def record_llm_call(self, provider: str, model: str, cost_usd: float, duration_s: float) -> None:
        self.counter("llm_call_total", {"provider": provider, "model": model}).inc()
        self.counter("llm_cost_usd_total", {"provider": provider, "model": model}).inc(cost_usd)
        self.histogram("llm_call_duration_seconds", {"provider": provider, "model": model}).observe(duration_s)

    def record_validation_score(self, artifact_type: str, score: float) -> None:
        self.histogram("validation_score", {"artifact_type": artifact_type}).observe(score)

    def record_task_result(self, task_type: str, success: bool) -> None:
        self.counter("task_total", {"task_type": task_type, "status": "success" if success else "failure"}).inc()

    # ── Snapshot ─────────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {k: c.value for k, c in self._counters.items()},
                "histograms": {
                    k: {"count": h.count, "sum": h.sum, "mean": h.mean}
                    for k, h in self._histograms.items()
                },
            }


_registry: MetricsRegistry | None = None


def get_metrics() -> MetricsRegistry:
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


def reset_metrics() -> None:
    global _registry
    _registry = None
