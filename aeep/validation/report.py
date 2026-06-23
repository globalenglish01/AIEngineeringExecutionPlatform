"""Validation report generator — Markdown and HTML output."""

from __future__ import annotations

from aeep.validation.models import GateDecision, Severity, ValidationResult


class ValidationReport:
    """Renders a ValidationResult as Markdown or HTML."""

    def __init__(self, result: ValidationResult) -> None:
        self._r = result

    def to_markdown(self) -> str:
        r = self._r
        decision_emoji = {"pass": "✅", "warn": "⚠️", "block": "❌"}.get(
            r.gate_decision.value, "?"
        )

        lines = [
            f"# Validation Report",
            f"",
            f"**Artifact**: `{r.artifact_id}`  ",
            f"**Overall Score**: {r.score:.1f}/100  ",
            f"**Decision**: {decision_emoji} {r.gate_decision.value.upper()}  ",
            f"**Errors**: {r.error_count}  **Warnings**: {r.warning_count}",
            f"",
        ]

        if r.dimensions:
            lines += ["## Dimension Scores", ""]
            lines += ["| Dimension | Score | Weight |", "| --- | --- | --- |"]
            for d in r.dimensions:
                bar = "█" * int(d.score / 10) + "░" * (10 - int(d.score / 10))
                lines.append(f"| {d.name} | {d.score:.1f} `{bar}` | {d.weight:.1f} |")
            lines.append("")

        if r.issues:
            lines += ["## Issues", ""]
            for issue in r.issues:
                icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    issue.severity.value, "•"
                )
                lines.append(f"- {icon} **{issue.severity.value.upper()}**: {issue.message}")
                if issue.suggestion:
                    lines.append(f"  - 💡 {issue.suggestion}")
            lines.append("")
        else:
            lines += ["## Issues", "", "_No issues found._", ""]

        return "\n".join(lines)

    def to_html(self) -> str:
        md = self.to_markdown()
        # Minimal Markdown → HTML conversion
        html_lines = ["<html><head><meta charset='utf-8'></head><body><pre>"]
        html_lines.append(md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        html_lines.append("</pre></body></html>")
        return "\n".join(html_lines)
