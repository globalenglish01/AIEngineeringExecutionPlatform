"""Consistency validator — cross-document terminology and reference checks."""

from __future__ import annotations

import re
from typing import Any

from aeep.validation.models import (
    DimensionScore,
    Severity,
    ValidationIssue,
    ValidationRule,
)


class ConsistencyValidator:
    """Checks terminology and reference consistency within a document."""

    async def validate(self, content: str, rule: ValidationRule) -> DimensionScore:
        cfg = rule.config
        issues: list[ValidationIssue] = []
        deductions = 0.0

        # Terminology consistency
        term_map = cfg.get("term_map", {})  # preferred → [aliases]
        for preferred, aliases in term_map.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", content, re.IGNORECASE):
                    issues.append(
                        ValidationIssue(
                            Severity.WARNING,
                            f"Inconsistent term: use '{preferred}' instead of '{alias}'",
                            dimension="terminology",
                            suggestion=f"Replace '{alias}' with '{preferred}' throughout",
                        )
                    )
                    deductions += 5.0

        # Reference consistency — check that [[Ref]] or (see Section X) targets exist
        required_sections = cfg.get("required_sections", [])
        for section in required_sections:
            if section.lower() not in content.lower():
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        f"Referenced section missing: '{section}'",
                        dimension="references",
                        suggestion=f"Add section '{section}' or remove the reference",
                    )
                )
                deductions += 10.0

        # Duplicate heading check
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        seen: set[str] = set()
        for h in headings:
            normalized = h.strip().lower()
            if normalized in seen:
                issues.append(
                    ValidationIssue(
                        Severity.WARNING,
                        f"Duplicate heading: '{h.strip()}'",
                        dimension="structure",
                        suggestion="Remove or rename duplicate headings",
                    )
                )
                deductions += 5.0
            seen.add(normalized)

        return DimensionScore(
            name=rule.name,
            score=max(0.0, 100.0 - deductions),
            weight=rule.weight,
            issues=issues,
        )
