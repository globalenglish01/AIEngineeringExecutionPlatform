"""Schema validator — JSON schema + text structure rules."""

from __future__ import annotations

from typing import Any

from aeep.validation.models import (
    DimensionScore,
    Severity,
    ValidationIssue,
    ValidationRule,
)


class SchemaValidator:
    """Validates artifacts against JSON schemas or structural text rules."""

    async def validate(
        self, content: Any, rule: ValidationRule
    ) -> DimensionScore:
        cfg = rule.config
        issues: list[ValidationIssue] = []
        score = 100.0

        # JSON schema validation
        if "json_schema" in cfg:
            score, issues = self._validate_json(content, cfg["json_schema"])
        # Text structure validation
        elif isinstance(content, str):
            score, issues = self._validate_text_structure(content, cfg)

        return DimensionScore(
            name=rule.name,
            score=score,
            weight=rule.weight,
            issues=issues,
        )

    def _validate_json(
        self, content: Any, schema: dict[str, Any]
    ) -> tuple[float, list[ValidationIssue]]:
        try:
            import jsonschema  # type: ignore[import]
        except ImportError:
            return 50.0, [
                ValidationIssue(Severity.WARNING, "jsonschema not installed; skipping JSON validation")
            ]

        issues: list[ValidationIssue] = []
        try:
            if isinstance(content, str):
                import json
                content = json.loads(content)
            jsonschema.validate(instance=content, schema=schema)
            return 100.0, []
        except jsonschema.ValidationError as e:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Schema violation: {e.message}",
                    dimension="schema",
                    suggestion=f"Fix field: {' → '.join(str(p) for p in e.absolute_path)}",
                )
            )
            return 0.0, issues
        except Exception as e:
            return 0.0, [ValidationIssue(Severity.ERROR, str(e), dimension="schema")]

    def _validate_text_structure(
        self, text: str, cfg: dict[str, Any]
    ) -> tuple[float, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []
        deductions = 0.0

        words = text.split()
        word_count = len(words)

        min_sections = cfg.get("min_sections")
        if min_sections is not None:
            section_count = text.count("\n#")
            if section_count < min_sections:
                issues.append(
                    ValidationIssue(
                        Severity.WARNING,
                        f"Expected ≥{min_sections} sections, found {section_count}",
                        dimension="structure",
                        suggestion="Add more section headings (## Heading)",
                    )
                )
                deductions += 10.0

        min_words = cfg.get("min_words")
        if min_words and word_count < min_words:
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    f"Too short: {word_count} words < {min_words} required",
                    dimension="length",
                    suggestion=f"Expand content to at least {min_words} words",
                )
            )
            deductions += 30.0

        max_words = cfg.get("max_words")
        if max_words and word_count > max_words:
            issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    f"Too long: {word_count} words > {max_words} limit",
                    dimension="length",
                    suggestion=f"Trim to under {max_words} words",
                )
            )
            deductions += 10.0

        return max(0.0, 100.0 - deductions), issues
