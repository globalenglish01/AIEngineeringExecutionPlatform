"""Tests for CLI commands using Typer test client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestCLIValidate:
    def test_validate_good_file(self, tmp_path: Path):
        artifact = tmp_path / "chapter.md"
        artifact.write_text(("This is a great Python tutorial with lots of content. " * 30))
        result = runner.invoke(app, ["validate", str(artifact), "--min-words", "50"])
        assert result.exit_code == 0
        assert "Validation Report" in result.output

    def test_validate_short_file(self, tmp_path: Path):
        artifact = tmp_path / "short.md"
        artifact.write_text("Too short.")
        result = runner.invoke(app, ["validate", str(artifact), "--min-words", "100"])
        # Short content → fails → exit 1
        assert result.exit_code == 1

    def test_validate_nonexistent_file(self, tmp_path: Path):
        result = runner.invoke(app, ["validate", str(tmp_path / "ghost.md")])
        assert result.exit_code != 0

    def test_validate_saves_report(self, tmp_path: Path):
        artifact = tmp_path / "doc.md"
        artifact.write_text("word " * 200)
        report_file = tmp_path / "report.md"
        result = runner.invoke(app, [
            "validate", str(artifact),
            "--min-words", "50",
            "--output", str(report_file),
        ])
        assert report_file.exists()


class TestCLIStatus:
    def test_status_nonexistent_run(self, tmp_path: Path):
        db = tmp_path / "state.db"
        result = runner.invoke(app, ["status", "nonexistent-run-id", "--db", str(db)])
        assert result.exit_code != 0


class TestCLIBenchmark:
    def test_benchmark_run_book_chapter(self, tmp_path: Path):
        db = tmp_path / "bench.db"
        result = runner.invoke(app, [
            "benchmark", "run", "book_chapter",
            "--db", str(db),
        ])
        # Should succeed (no actual LLM needed — uses heuristic scorer)
        assert result.exit_code in (0, 1)  # 0=pass, 1=regression
        assert "Benchmark Report" in result.output

    def test_benchmark_report_empty(self, tmp_path: Path):
        db = tmp_path / "bench.db"
        result = runner.invoke(app, ["benchmark", "report", "nonexistent", "--db", str(db)])
        assert "No benchmark history" in result.output


class TestCLIProvider:
    def test_provider_list_no_providers(self):
        from aeep.providers.registry import reset_registry
        reset_registry()
        result = runner.invoke(app, ["provider", "list"])
        assert result.exit_code == 0
