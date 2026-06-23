"""Unit tests for benchmark system."""

from __future__ import annotations

import pytest
from pathlib import Path

from aeep.benchmark.leaderboard import Leaderboard
from aeep.benchmark.runner import BenchmarkReport, BenchmarkRunner, TaskResult
from aeep.benchmark.suite import BenchmarkSuite, BenchmarkTask
from aeep.benchmark.tracker import BenchmarkTracker


def _make_suite(n_tasks: int = 3) -> BenchmarkSuite:
    return BenchmarkSuite(
        suite_id="test_suite",
        name="Test Suite",
        tasks=[
            BenchmarkTask(
                task_id=f"t{i}",
                name=f"Task {i}",
                description=f"Task {i} description",
                input=f"input {i}",
                expected_keywords=["python", "code"],
                min_score=60.0,
            )
            for i in range(n_tasks)
        ],
    )


def _make_report(suite_id: str, mean_score: float, run_id: str | None = None) -> BenchmarkReport:
    import uuid
    rid = run_id or uuid.uuid4().hex[:8]
    tasks = [
        TaskResult(f"t{i}", f"Task {i}", score=mean_score, passed=mean_score >= 60, duration_ms=10)
        for i in range(3)
    ]
    return BenchmarkReport(
        suite_id=suite_id,
        suite_name="Test Suite",
        run_id=rid,
        started_at="2025-01-01T00:00:00+00:00",
        finished_at="2025-01-01T00:00:01+00:00",
        task_results=tasks,
    )


class TestBenchmarkSuite:
    def test_from_yaml(self, tmp_path: Path):
        yaml_content = """
suite_id: my_suite
name: My Suite
tasks:
  - task_id: t1
    name: Task 1
    input: "write something"
    expected_keywords: [python]
    min_score: 70
"""
        p = tmp_path / "my_suite.yaml"
        p.write_text(yaml_content)
        suite = BenchmarkSuite.from_yaml(p)
        assert suite.suite_id == "my_suite"
        assert len(suite.tasks) == 1
        assert suite.tasks[0].min_score == 70.0

    def test_default_min_score(self):
        suite = _make_suite()
        assert all(t.min_score == 60.0 for t in suite.tasks)


class TestBenchmarkRunner:
    @pytest.mark.asyncio
    async def test_runs_all_tasks(self):
        suite = _make_suite(3)
        runner = BenchmarkRunner()
        report = await runner.run(suite)
        assert len(report.task_results) == 3

    @pytest.mark.asyncio
    async def test_custom_generator(self):
        suite = _make_suite(2)
        runner = BenchmarkRunner()

        async def gen(inp: str) -> str:
            return "python code example with lots of words " * 20

        report = await runner.run(suite, generator=gen)
        assert all(r.score > 50 for r in report.task_results)

    @pytest.mark.asyncio
    async def test_keyword_scoring(self):
        suite = BenchmarkSuite(
            suite_id="s",
            name="S",
            tasks=[
                BenchmarkTask("t1", "T1", "", "input",
                               expected_keywords=["python", "async"], min_score=40.0)
            ],
        )
        runner = BenchmarkRunner()

        async def gen(_: str) -> str:
            return "This uses python and async features"

        report = await runner.run(suite, generator=gen)
        assert report.task_results[0].passed  # both keywords present

    def test_mean_score(self):
        report = _make_report("s", 80.0)
        assert report.mean_score == 80.0

    def test_pass_rate(self):
        report = _make_report("s", 80.0)
        assert report.pass_rate == 1.0

    def test_to_markdown(self):
        report = _make_report("s", 75.0)
        md = report.to_markdown()
        assert "Benchmark Report" in md
        assert "75.0" in md

    @pytest.mark.asyncio
    async def test_generator_exception_captured(self):
        suite = _make_suite(1)
        runner = BenchmarkRunner()

        async def bad_gen(_: str) -> str:
            raise RuntimeError("generator failed")

        report = await runner.run(suite, generator=bad_gen)
        assert report.task_results[0].error != ""
        assert report.task_results[0].score == 0.0


class TestBenchmarkTracker:
    def test_save_and_retrieve(self):
        tracker = BenchmarkTracker()
        report = _make_report("suite1", 80.0, run_id="abc123")
        tracker.save(report)
        loaded = tracker.get_run("abc123")
        assert loaded is not None
        assert loaded.mean_score == 80.0

    def test_get_latest(self):
        tracker = BenchmarkTracker()
        tracker.save(_make_report("suite1", 75.0, run_id="r1"))
        tracker.save(_make_report("suite1", 82.0, run_id="r2"))
        latest = tracker.get_latest("suite1", n=1)
        assert len(latest) == 1

    def test_no_regression_when_improving(self):
        tracker = BenchmarkTracker()
        tracker.save(_make_report("suite1", 70.0))
        new_report = _make_report("suite1", 80.0)
        alert = tracker.check_regression(new_report, threshold=5.0)
        assert alert is None

    def test_regression_detected(self):
        tracker = BenchmarkTracker()
        tracker.save(_make_report("suite1", 80.0))
        new_report = _make_report("suite1", 60.0)
        alert = tracker.check_regression(new_report, threshold=5.0)
        assert alert is not None
        assert alert.score_delta < -5.0

    def test_trend_data(self):
        tracker = BenchmarkTracker()
        for score in [60.0, 70.0, 80.0]:
            tracker.save(_make_report("suite1", score))
        trend = tracker.trend_data("suite1", last_n=10)
        assert len(trend) == 3
        assert trend[0]["mean_score"] == 60.0


class TestLeaderboard:
    def test_rank_by_mean_score(self):
        lb = Leaderboard()
        lb.add(_make_report("s", 70.0), label="model_a")
        lb.add(_make_report("s", 85.0), label="model_b")
        lb.add(_make_report("s", 60.0), label="model_c")
        ranked = lb.rank()
        assert ranked[0].label == "model_b"
        assert ranked[-1].label == "model_c"

    def test_to_markdown(self):
        lb = Leaderboard()
        lb.add(_make_report("s", 75.0), label="gpt-4o")
        md = lb.to_markdown()
        assert "Leaderboard" in md
        assert "gpt-4o" in md

    def test_to_json(self):
        lb = Leaderboard()
        lb.add(_make_report("s", 75.0), label="gpt-4o")
        data = lb.to_json()
        assert data[0]["label"] == "gpt-4o"
        assert data[0]["mean_score"] == 75.0
