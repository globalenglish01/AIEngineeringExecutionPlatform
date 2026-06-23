"""End-to-end validation pipeline test."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from aeep.core.models.artifact import Artifact, ArtifactType
from aeep.core.models.message import CompletionResult
from aeep.validation.engine import ValidationEngine
from aeep.validation.models import GateDecision, RuleType, ValidationRule
from aeep.validation.quality_gate import GateRule, QualityGate
from aeep.validation.report import ValidationReport
from aeep.benchmark.runner import BenchmarkRunner
from aeep.benchmark.suite import BenchmarkSuite, BenchmarkTask
from aeep.benchmark.tracker import BenchmarkTracker

# ─── Sample chapter content ────────────────────────────────────────────────────

_GOOD_CHAPTER = """\
## Introduction to Python Asyncio

Python's asyncio library enables writing concurrent code using the async/await syntax.
This chapter explores the event loop, coroutines, and practical patterns for building
high-performance asynchronous applications.

## Understanding the Event Loop

The event loop is the core of asyncio. It schedules and runs coroutines, handling
I/O operations efficiently without blocking. When you call asyncio.run(), Python
creates an event loop and runs your coroutine inside it.

## Working with Coroutines

A coroutine is a function defined with async def. Inside it, you can await other
coroutines or awaitables. This allows Python to pause execution and resume later
when the awaited operation completes.

## Conclusion

Asyncio transforms how we write I/O-bound Python applications. By mastering
the event loop and coroutines, you can build fast, scalable systems.
""" * 3  # ~300 words


_BAD_CHAPTER = "TODO: write content here [PLACEHOLDER]"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def good_artifact() -> Artifact:
    return Artifact(
        artifact_type=ArtifactType.MARKDOWN,
        content=_GOOD_CHAPTER,
        metadata={"chapter": "asyncio"},
    )


@pytest.fixture
def bad_artifact() -> Artifact:
    return Artifact(
        artifact_type=ArtifactType.MARKDOWN,
        content=_BAD_CHAPTER,
        metadata={"chapter": "placeholder"},
    )


# ─── Validation Engine tests ───────────────────────────────────────────────────

class TestValidationEngineE2E:
    @pytest.mark.asyncio
    async def test_good_chapter_passes(self, good_artifact):
        engine = ValidationEngine()
        rules = [
            ValidationRule("word_count", RuleType.RULE,
                           config={"min_words": 100, "no_placeholder": None}),
            ValidationRule("structure", RuleType.SCHEMA,
                           config={"min_sections": 2}),
        ]
        result = await engine.validate(good_artifact, rules)
        assert result.score >= 70.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_bad_chapter_blocked(self, bad_artifact):
        engine = ValidationEngine()
        rules = [
            ValidationRule("word_count", RuleType.RULE,
                           config={"min_words": 50, "no_placeholder": None}),
        ]
        result = await engine.validate(bad_artifact, rules)
        # Has placeholder → no_placeholder fails → score 0 → BLOCK
        assert result.score < 70.0

    @pytest.mark.asyncio
    async def test_quality_gate_applied(self, good_artifact):
        engine = ValidationEngine()
        rules = [
            ValidationRule("length", RuleType.RULE, config={"min_words": 50}),
        ]
        result = await engine.validate(good_artifact, rules)

        gate = QualityGate(
            name="chapter_gate",
            hard_gates=[GateRule("hard", min_score=60.0)],
            soft_gates=[GateRule("soft", min_score=90.0)],
        )
        decision = gate.evaluate(result)
        assert decision in (GateDecision.PASS, GateDecision.WARN)

    @pytest.mark.asyncio
    async def test_llm_validator_mock(self, good_artifact):
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=CompletionResult(
                content='{"factual_accuracy": 85, "completeness": 78, "clarity": 90, "practicality": 75, "innovation": 70}',
                model="gpt-4o-mini",
                provider_name="mock",
                input_tokens=50,
                output_tokens=30,
                finish_reason="stop",
                duration_ms=1,
            )
        )
        engine = ValidationEngine(llm_provider=mock_provider)
        rules = [
            ValidationRule("llm_quality", RuleType.LLM,
                           config={"num_samples": 1}),
        ]
        result = await engine.validate(good_artifact, rules)
        assert result.score > 0
        assert len(result.dimensions) == 1
        assert result.dimensions[0].score > 70.0


# ─── Report generation ────────────────────────────────────────────────────────

class TestValidationReport:
    @pytest.mark.asyncio
    async def test_markdown_report(self, good_artifact):
        engine = ValidationEngine()
        rules = [ValidationRule("length", RuleType.RULE, config={"min_words": 50})]
        result = await engine.validate(good_artifact, rules)
        report = ValidationReport(result)
        md = report.to_markdown()
        assert "Validation Report" in md
        assert "Decision" in md

    @pytest.mark.asyncio
    async def test_html_report(self, good_artifact):
        engine = ValidationEngine()
        rules = [ValidationRule("length", RuleType.RULE, config={"min_words": 50})]
        result = await engine.validate(good_artifact, rules)
        report = ValidationReport(result)
        html = report.to_html()
        assert "<html>" in html
        assert "Validation Report" in html


# ─── Benchmark integration ────────────────────────────────────────────────────

class TestBenchmarkIntegration:
    @pytest.mark.asyncio
    async def test_suite_run_and_track(self):
        suite = BenchmarkSuite(
            suite_id="e2e_test",
            name="E2E Test Suite",
            tasks=[
                BenchmarkTask(
                    task_id="t1",
                    name="Write Intro",
                    description="Intro paragraph",
                    input="Write a short introduction about Python.",
                    expected_keywords=["Python", "programming"],
                    min_score=40.0,
                ),
                BenchmarkTask(
                    task_id="t2",
                    name="Write Conclusion",
                    description="Conclusion paragraph",
                    input="Write a short conclusion about Python.",
                    expected_keywords=["summary", "learned"],
                    min_score=30.0,
                ),
            ],
        )

        async def generator(inp: str) -> str:
            return (
                "Python programming is a versatile language. "
                "In summary, we learned key concepts. " * 20
            )

        runner = BenchmarkRunner()
        report = await runner.run(suite, generator=generator)

        assert len(report.task_results) == 2
        assert report.mean_score > 0

        tracker = BenchmarkTracker()
        tracker.save(report)

        # Verify no regression on first run (no baseline)
        alert = tracker.check_regression(report, threshold=5.0)
        assert alert is None

    @pytest.mark.asyncio
    async def test_regression_detection(self):
        """Manually create quality drop and verify regression is detected."""
        tracker = BenchmarkTracker()

        # Good run (score 80)
        good = BenchmarkSuite(
            suite_id="reg_test",
            name="Regression Test",
            tasks=[BenchmarkTask("t1", "T1", "", "input",
                                  expected_keywords=["python"], min_score=50.0)],
        )
        runner = BenchmarkRunner()

        async def good_gen(_: str) -> str:
            return "python code " * 50  # ~100 words

        good_report = await runner.run(good, generator=good_gen)
        tracker.save(good_report)

        async def bad_gen(_: str) -> str:
            return "x"  # terrible output

        bad_report = await runner.run(good, generator=bad_gen)
        alert = tracker.check_regression(bad_report, threshold=5.0)
        assert alert is not None
        assert alert.score_delta < 0
