"""Validation tool — run heuristic quality check on text output."""

from __future__ import annotations

from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class ValidationTool(BaseTool):
    name = "validation_tool"
    description = "Validate the quality of a text output and return a score with issues."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Text content to validate."},
            "min_score": {
                "type": "number",
                "description": "Minimum acceptable score 0-100 (default 70).",
            },
            "criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of validation criteria.",
            },
        },
        "required": ["content"],
    }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        content = args.get("content", "")
        min_score = float(args.get("min_score", 70.0))

        if not content:
            return ToolResult(
                success=False,
                output={"score": 0, "passed": False, "issues": ["Content is empty"]},
                error="Empty content",
            )

        word_count = len(content.split())
        score = min(100.0, 50.0 + word_count / 10.0)
        issues: list[str] = []

        if word_count < 10:
            issues.append(f"Content too short ({word_count} words)")
        if len(content) > 50_000:
            issues.append("Content exceeds 50k characters")

        passed = score >= min_score and not any(
            "too short" in i for i in issues
        )
        return ToolResult(
            success=passed,
            output={"score": round(score, 1), "passed": passed, "issues": issues},
            error="" if passed else f"Score {score:.1f} < {min_score}",
        )