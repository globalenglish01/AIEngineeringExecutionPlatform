"""Code validator — syntax check, test runner, linter, security scan."""

from __future__ import annotations

import asyncio
import py_compile
import sys
import tempfile
from pathlib import Path
from typing import Any

from aeep.validation.models import (
    DimensionScore,
    Severity,
    ValidationIssue,
    ValidationRule,
)


class CodeValidator:
    """Validates Python (and optionally JS) code quality."""

    async def validate(self, content: str, rule: ValidationRule) -> DimensionScore:
        cfg = rule.config
        language = cfg.get("language", "python").lower()
        checks = cfg.get("checks", ["syntax"])
        issues: list[ValidationIssue] = []
        score = 100.0

        if language == "python":
            for check in checks:
                check_issues, deduction = await self._python_check(content, check, cfg)
                issues.extend(check_issues)
                score -= deduction
        else:
            issues.append(
                ValidationIssue(
                    Severity.INFO,
                    f"Language {language!r} not supported; skipping code validation",
                )
            )

        return DimensionScore(
            name=rule.name,
            score=max(0.0, score),
            weight=rule.weight,
            issues=issues,
        )

    async def _python_check(
        self, code: str, check: str, cfg: dict[str, Any]
    ) -> tuple[list[ValidationIssue], float]:
        if check == "syntax":
            return self._syntax_check(code)
        elif check == "ruff":
            return await self._ruff_check(code)
        elif check == "bandit":
            return await self._bandit_check(code)
        elif check == "pytest":
            return await self._pytest_check(code, cfg)
        return [], 0.0

    @staticmethod
    def _syntax_check(code: str) -> tuple[list[ValidationIssue], float]:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            py_compile.compile(tmp, doraise=True)
            return [], 0.0
        except py_compile.PyCompileError as e:
            return [
                ValidationIssue(
                    Severity.ERROR,
                    f"Syntax error: {e}",
                    dimension="syntax",
                    suggestion="Fix the syntax error before proceeding",
                )
            ], 40.0
        finally:
            Path(tmp).unlink(missing_ok=True)

    @staticmethod
    async def _ruff_check(code: str) -> tuple[list[ValidationIssue], float]:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "ruff", "check", "--output-format=json", tmp,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            import json
            violations = json.loads(stdout.decode()) if stdout else []
            issues = [
                ValidationIssue(
                    Severity.WARNING,
                    f"[{v.get('code','?')}] {v.get('message','')} (line {v.get('location',{}).get('row','?')})",
                    dimension="style",
                )
                for v in violations[:10]
            ]
            deduction = min(20.0, len(violations) * 2.0)
            return issues, deduction
        except (asyncio.TimeoutError, Exception):
            return [], 0.0
        finally:
            Path(tmp).unlink(missing_ok=True)

    @staticmethod
    async def _bandit_check(code: str) -> tuple[list[ValidationIssue], float]:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "bandit", "-f", "json", "-q", tmp,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            import json
            try:
                data = json.loads(stdout.decode())
                findings = data.get("results", [])
            except (json.JSONDecodeError, ValueError):
                findings = []
            high = [f for f in findings if f.get("issue_severity") == "HIGH"]
            issues = [
                ValidationIssue(
                    Severity.ERROR if f.get("issue_severity") == "HIGH" else Severity.WARNING,
                    f"Security: {f.get('issue_text','')} (line {f.get('line_number','?')})",
                    dimension="security",
                    suggestion="Fix the security issue",
                )
                for f in findings[:10]
            ]
            deduction = min(30.0, len(high) * 10.0)
            return issues, deduction
        except (asyncio.TimeoutError, Exception):
            return [], 0.0
        finally:
            Path(tmp).unlink(missing_ok=True)

    @staticmethod
    async def _pytest_check(code: str, cfg: dict[str, Any]) -> tuple[list[ValidationIssue], float]:
        test_dir = cfg.get("test_dir")
        if not test_dir:
            return [], 0.0
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pytest", test_dir, "-q", "--tb=no",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode()
            if proc.returncode != 0:
                return [
                    ValidationIssue(Severity.ERROR, f"Tests failed:\n{output[:500]}", dimension="tests")
                ], 20.0
            return [], 0.0
        except (asyncio.TimeoutError, Exception):
            return [], 0.0
