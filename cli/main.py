"""AEEP CLI — entry point for all platform commands."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="platform",
    help="AI Engineering Execution Platform CLI",
    no_args_is_help=True,
)
benchmark_app = typer.Typer(help="Benchmark commands")
provider_app = typer.Typer(help="Provider commands")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(provider_app, name="provider")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def _echo_json(data: dict) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


# ─── Workflow commands ─────────────────────────────────────────────────────────

@app.command("run")
def cmd_run(
    workflow_name: str = typer.Argument(..., help="Workflow name (YAML template name without .yaml)"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="JSON input file"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Run a workflow from a YAML template."""
    from aeep.workflow.dag import DAG
    from aeep.workflow.runner import WorkflowRunner
    from aeep.workflow.state import WorkflowStateStore

    context: dict = {}
    if input_file:
        if not input_file.exists():
            typer.echo(f"Error: input file not found: {input_file}", err=True)
            raise typer.Exit(1)
        with open(input_file) as f:
            context = json.load(f)

    # Look for workflow template
    template_path = Path("workflows/templates") / f"{workflow_name}.yaml"
    if not template_path.exists():
        typer.echo(f"Error: workflow template not found: {template_path}", err=True)
        raise typer.Exit(1)

    db_path = (output_dir or Path(".")) / "workflow_state.db"
    store = WorkflowStateStore(db_path)

    typer.echo(f"▶ Running workflow: {workflow_name}")

    # Build a minimal DAG from template metadata (real implementation would parse YAML)
    dag = DAG()

    async def _run_workflow():
        runner = WorkflowRunner(workflow_name, dag, state_store=store)
        run = await runner.run(context)
        return run

    run = _run(_run_workflow())
    typer.echo(f"✓ Completed run: {run.run_id} — status: {run.status.value}")
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{run.run_id}.json"
        out_file.write_text(json.dumps(run.final_context, indent=2, default=str))
        typer.echo(f"  Output saved to: {out_file}")


@app.command("status")
def cmd_status(
    run_id: str = typer.Argument(..., help="Run ID to query"),
    db: Path = typer.Option(Path("workflow_state.db"), "--db", help="State DB path"),
):
    """Query the status of a workflow run."""
    from aeep.workflow.state import WorkflowStateStore
    store = WorkflowStateStore(db)
    run = store.load_run(run_id)
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(1)
    _echo_json({
        "run_id": run.run_id,
        "workflow": run.workflow_name,
        "status": run.status.value,
        "nodes": {nid: nr.status.value for nid, nr in run.node_runs.items()},
    })


@app.command("resume")
def cmd_resume(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
    db: Path = typer.Option(Path("workflow_state.db"), "--db", help="State DB path"),
):
    """Resume a paused or failed workflow run."""
    from aeep.workflow.dag import DAG
    from aeep.workflow.runner import WorkflowRunner
    from aeep.workflow.state import WorkflowStateStore

    store = WorkflowStateStore(db)
    existing = store.load_run(run_id)
    if existing is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(1)

    dag = DAG()

    async def _resume():
        runner = WorkflowRunner(existing.workflow_name, dag, state_store=store)
        return await runner.run(resume_run_id=run_id)

    run = _run(_resume())
    typer.echo(f"✓ Resumed — final status: {run.status.value}")


# ─── Validation commands ───────────────────────────────────────────────────────

@app.command("validate")
def cmd_validate(
    artifact_path: Path = typer.Argument(..., help="Path to artifact file to validate"),
    min_words: int = typer.Option(100, "--min-words", help="Minimum word count"),
    no_placeholder: bool = typer.Option(True, "--no-placeholder/--allow-placeholder"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save report to file"),
):
    """Validate an artifact file and print a quality report."""
    from aeep.core.models.artifact import Artifact, ArtifactType
    from aeep.validation.engine import ValidationEngine
    from aeep.validation.models import RuleType, ValidationRule
    from aeep.validation.report import ValidationReport

    if not artifact_path.exists():
        typer.echo(f"Error: file not found: {artifact_path}", err=True)
        raise typer.Exit(1)

    content = artifact_path.read_text(encoding="utf-8")
    artifact = Artifact(artifact_type=ArtifactType.MARKDOWN, content=content)

    rules: list[ValidationRule] = [
        ValidationRule("length", RuleType.RULE, config={"min_words": min_words}),
    ]
    if no_placeholder:
        rules.append(ValidationRule("clean", RuleType.RULE, config={"no_placeholder": None}))

    async def _validate():
        engine = ValidationEngine()
        return await engine.validate(artifact, rules)

    result = _run(_validate())
    report = ValidationReport(result)
    md = report.to_markdown()
    typer.echo(md)

    if output:
        output.write_text(md, encoding="utf-8")
        typer.echo(f"Report saved to: {output}")

    raise typer.Exit(0 if result.passed else 1)


# ─── Benchmark commands ────────────────────────────────────────────────────────

@benchmark_app.command("run")
def cmd_benchmark_run(
    suite_name: str = typer.Argument(..., help="Suite name (without _suite.yaml)"),
    db: Path = typer.Option(Path("benchmark_history.db"), "--db"),
    threshold: float = typer.Option(5.0, "--threshold", help="Regression threshold"),
):
    """Run a benchmark suite and check for regressions."""
    from aeep.benchmark.runner import BenchmarkRunner
    from aeep.benchmark.suite import BenchmarkSuite
    from aeep.benchmark.tracker import BenchmarkTracker

    suite_path = Path("aeep/benchmark/suites") / f"{suite_name}_suite.yaml"
    if not suite_path.exists():
        typer.echo(f"Error: suite not found: {suite_path}", err=True)
        raise typer.Exit(1)

    suite = BenchmarkSuite.from_yaml(suite_path)
    runner = BenchmarkRunner()
    report = _run(runner.run(suite))

    tracker = BenchmarkTracker(db)
    regression = tracker.check_regression(report, threshold=threshold)
    tracker.save(report)

    typer.echo(report.to_markdown())
    typer.echo(f"\nMean score: {report.mean_score:.1f} | Pass rate: {report.pass_rate*100:.0f}%")

    if regression:
        typer.echo(f"\n⚠ Regression: {regression.score_delta:.1f} points vs baseline", err=True)
        raise typer.Exit(1)


@benchmark_app.command("report")
def cmd_benchmark_report(
    suite_name: str = typer.Argument(..., help="Suite ID"),
    db: Path = typer.Option(Path("benchmark_history.db"), "--db"),
    last_n: int = typer.Option(5, "--last", help="Show last N runs"),
):
    """Show benchmark history for a suite."""
    from aeep.benchmark.tracker import BenchmarkTracker
    tracker = BenchmarkTracker(db)
    trend = tracker.trend_data(suite_name, last_n=last_n)
    if not trend:
        typer.echo("No benchmark history found.")
        return
    typer.echo(f"Benchmark history for '{suite_name}' (last {last_n}):\n")
    for row in trend:
        typer.echo(f"  {row['started_at'][:19]}  score={row['mean_score']:.1f}  pass_rate={row['pass_rate']*100:.0f}%")


# ─── Provider commands ─────────────────────────────────────────────────────────

@provider_app.command("list")
def cmd_provider_list():
    """List all registered providers."""
    from aeep.providers.registry import get_registry
    registry = get_registry()
    names = registry.list_providers() if hasattr(registry, "list_providers") else []
    if not names:
        typer.echo("No providers registered. Configure providers in config/providers.yaml")
        return
    for name in names:
        typer.echo(f"  • {name}")


@provider_app.command("health")
def cmd_provider_health():
    """Check health of all registered providers."""
    from aeep.providers.registry import get_registry
    registry = get_registry()

    async def _health():
        names = registry.list_providers() if hasattr(registry, "list_providers") else []
        results = {}
        for name in names:
            try:
                p = registry.get(name)
                hr = await p.health_check()
                results[name] = hr.healthy
            except Exception as e:
                results[name] = f"error: {e}"
        return results

    results = _run(_health())
    if not results:
        typer.echo("No providers registered.")
        return
    for name, status in results.items():
        icon = "✓" if status is True else "✗"
        typer.echo(f"  {icon} {name}: {status}")


if __name__ == "__main__":
    app()
