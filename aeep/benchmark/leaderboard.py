"""Leaderboard — compare provider/config scores, export Markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aeep.benchmark.runner import BenchmarkReport


@dataclass
class LeaderboardEntry:
    label: str                    # e.g. "gpt-4o / template_v2"
    suite_id: str
    run_id: str
    mean_score: float
    pass_rate: float
    dimension_scores: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class Leaderboard:
    """Ranks benchmark reports by overall or per-dimension score."""

    def __init__(self) -> None:
        self._entries: list[LeaderboardEntry] = []

    def add(self, report: BenchmarkReport, label: str = "") -> None:
        entry = LeaderboardEntry(
            label=label or report.run_id,
            suite_id=report.suite_id,
            run_id=report.run_id,
            mean_score=report.mean_score,
            pass_rate=report.pass_rate,
            metadata=report.metadata,
        )
        self._entries.append(entry)

    def rank(self, by: str = "mean_score") -> list[LeaderboardEntry]:
        return sorted(self._entries, key=lambda e: getattr(e, by, 0.0), reverse=True)

    def to_markdown(self, by: str = "mean_score", top_n: int = 20) -> str:
        ranked = self.rank(by)[:top_n]
        lines = [
            f"# Leaderboard (sorted by {by})",
            "",
            "| # | Label | Suite | Score | Pass Rate |",
            "| --- | --- | --- | --- | --- |",
        ]
        for i, entry in enumerate(ranked, 1):
            lines.append(
                f"| {i} | {entry.label} | {entry.suite_id} | "
                f"{entry.mean_score:.1f} | {entry.pass_rate * 100:.0f}% |"
            )
        return "\n".join(lines)

    def to_json(self) -> list[dict[str, Any]]:
        return [
            {
                "label": e.label,
                "suite_id": e.suite_id,
                "run_id": e.run_id,
                "mean_score": e.mean_score,
                "pass_rate": e.pass_rate,
            }
            for e in self.rank()
        ]
