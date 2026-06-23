"""Demo: validate a fixed chapter artifact through the full pipeline.

This script proves the platform works end-to-end without a real LLM call
by using a high-quality pre-written sample chapter.

Run::

    uv run python scripts/demo_task.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

SAMPLE_CHAPTER = """\
# Python Asyncio Best Practices

## Introduction

Asyncio is Python's built-in framework for writing concurrent code using the
async/await syntax. Introduced in Python 3.4 and significantly improved through
subsequent versions, asyncio enables developers to handle thousands of I/O-bound
operations simultaneously within a single thread.

## Understanding the Event Loop

The event loop is the beating heart of asyncio. It is responsible for scheduling
coroutines, handling I/O callbacks, and managing tasks. When you call
`asyncio.run()`, Python creates a new event loop, executes your top-level
coroutine, and cleanly shuts the loop down when it completes.

Best practice: avoid creating event loops manually. Always use `asyncio.run()`
at the top level of your application.

## Coroutines and Tasks

A coroutine is a function declared with `async def`. Coroutines are lazy — they
don't execute until awaited or wrapped in a `Task`. Use `asyncio.create_task()`
to schedule coroutines for concurrent execution:

```python
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

async def main():
    # Run three fetches concurrently
    tasks = [asyncio.create_task(fetch_data(url)) for url in urls]
    results = await asyncio.gather(*tasks)
```

## Avoiding Common Pitfalls

**Blocking the event loop**: Never call blocking I/O (file reads, `time.sleep`,
CPU-heavy computations) directly in a coroutine. Use `asyncio.to_thread()` for
blocking calls or `loop.run_in_executor()` for CPU-bound work.

**Forgetting to await**: A missing `await` returns the coroutine object rather
than its result — use type checkers and linters to catch this early.

**Unhandled task exceptions**: Tasks that raise exceptions without being awaited
can silently swallow errors. Always `await` your tasks or attach a callback with
`task.add_done_callback()`.

## Structured Concurrency with TaskGroup

Python 3.11 introduced `asyncio.TaskGroup`, which provides structured concurrency:
all tasks in the group are cancelled if any one of them raises an exception.

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        task_a = tg.create_task(step_a())
        task_b = tg.create_task(step_b())
    # Both tasks are guaranteed to have completed (or the exception propagated)
```

## Testing Async Code

Use `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml` to
eliminate boilerplate. Mock external I/O with `AsyncMock` from `unittest.mock`.

## Conclusion

Asyncio unlocks high-concurrency Python applications without the complexity of
multi-threading. By following these best practices — using `asyncio.run()`,
preferring `create_task` over raw coroutine awaits, and avoiding blocking calls
— you can build fast, reliable asynchronous systems with confidence.

Key takeaways:
- Always use `asyncio.run()` as your top-level entry point
- Prefer `asyncio.gather()` and `TaskGroup` for concurrent execution
- Keep CPU-bound work off the event loop
- Test with pytest-asyncio for clean, readable async tests
"""


async def main() -> int:
    from aeep.core.models.artifact import Artifact, ArtifactType
    from aeep.validation.engine import ValidationEngine
    from aeep.validation.models import RuleType, ValidationRule
    from aeep.validation.quality_gate import GateRule, QualityGate
    from aeep.validation.report import ValidationReport
    from aeep.observability.metrics import get_metrics

    print("=" * 60)
    print("AEEP Demo Task: Validate a Python Asyncio Best Practices Chapter")
    print("=" * 60)

    artifact = Artifact(artifact_type=ArtifactType.MARKDOWN, content=SAMPLE_CHAPTER)
    word_count = len(SAMPLE_CHAPTER.split())
    print(f"\n[Artifact] Word count: {word_count}")

    rules = [
        ValidationRule("word_count", RuleType.RULE,
                       config={"min_words": 300}),
        ValidationRule("structure", RuleType.SCHEMA,
                       config={"min_sections": 4}),
        ValidationRule("consistency", RuleType.CONSISTENCY,
                       config={}),
    ]

    engine = ValidationEngine()
    result = await engine.validate(artifact, rules)

    gate = QualityGate(
        name="book_chapter",
        hard_gates=[GateRule("hard", min_score=75.0)],
        soft_gates=[GateRule("soft", min_score=90.0)],
    )
    gate_decision = gate.evaluate(result)

    report = ValidationReport(result)
    # Print ASCII-safe summary (avoid emoji on Windows cp932)
    print(f"Score:    {result.score:.1f}/100")
    print(f"Decision: {gate_decision.value.upper()}")
    print(f"Errors:   {result.error_count}  Warnings: {result.warning_count}")
    for dim in result.dimensions:
        print(f"  {dim.name}: {dim.score:.1f}")

    # Record metrics
    metrics = get_metrics()
    metrics.record_validation_score("book_chapter", result.score)
    metrics.record_task_result("write_chapter", success=result.passed)

    # Save report
    out_path = Path("outputs/demo_report.md")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(report.to_markdown(), encoding="utf-8")
    print(f"\nReport saved to: {out_path}")

    if result.score >= 80.0:
        print(f"\nSUCCESS: Quality score {result.score:.1f} >= 80.0")
        return 0
    else:
        print(f"\nBELOW TARGET: Quality score {result.score:.1f} < 80.0")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
