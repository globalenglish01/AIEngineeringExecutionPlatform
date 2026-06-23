"""CI benchmark script — run benchmark suite and detect regressions.

Usage::

    uv run python scripts/ci_benchmark.py --suite book_chapter --threshold 5.0

Exit codes:
    0 — all passed or only soft regressions
    1 — hard regression detected (score drop > threshold)
    2 — unexpected error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from aeep.benchmark.leaderboard import Leaderboard
from aeep.benchmark.runner import BenchmarkRunner
from aeep.benchmark.suite import BenchmarkSuite
from aeep.benchmark.tracker import BenchmarkTracker


async def main(args: argparse.Namespace) -> int:
    suite_path = (
        _ROOT / "aeep" / "benchmark" / "suites" / f"{args.suite}_suite.yaml"
    )
    if not suite_path.exists():
        print(f"ERROR: Suite file not found: {suite_path}", file=sys.stderr)
        return 2

    suite = BenchmarkSuite.from_yaml(suite_path)
    runner = BenchmarkRunner()
    report = await runner.run(suite, metadata={"ci": True, "suite": args.suite})

    tracker = BenchmarkTracker(db_path=args.db)
    regression = tracker.check_regression(report, threshold=args.threshold)
    tracker.save(report)

    print(report.to_markdown())
    print()
    print(f"Mean score: {report.mean_score:.1f} | Pass rate: {report.pass_rate * 100:.0f}%")

    if regression:
        print(
            f"\n⚠️  REGRESSION DETECTED: score dropped {regression.score_delta:.1f} points "
            f"(threshold: -{args.threshold})",
            file=sys.stderr,
        )
        if regression.task_regressions:
            print("Regressed tasks:", file=sys.stderr)
            for t in regression.task_regressions:
                print(f"  {t['task_id']}: {t['baseline']:.1f} → {t['current']:.1f}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEEP CI Benchmark")
    parser.add_argument("--suite", default="book_chapter", help="Suite name (without _suite.yaml)")
    parser.add_argument("--threshold", type=float, default=5.0, help="Regression threshold in score points")
    parser.add_argument("--db", default="benchmark_history.db", help="SQLite DB path for history")
    parsed = parser.parse_args()

    try:
        exit_code = asyncio.run(main(parsed))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        exit_code = 2

    sys.exit(exit_code)
