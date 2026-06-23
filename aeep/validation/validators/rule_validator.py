"""Rule validator — built-in + YAML-loadable text rules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from aeep.validation.models import (
    DimensionScore,
    Severity,
    ValidationIssue,
    ValidationRule,
)

# Built-in rule functions: (text, param) -> (passed, message)
_BUILTIN: dict[str, Any] = {}


def _rule(name: str):
    def decorator(fn):
        _BUILTIN[name] = fn
        return fn
    return decorator


@_rule("min_words")
def _min_words(text: str, param: Any) -> tuple[bool, str]:
    count = len(text.split())
    ok = count >= int(param)
    return ok, f"Word count {count} {'≥' if ok else '<'} {param}"


@_rule("max_words")
def _max_words(text: str, param: Any) -> tuple[bool, str]:
    count = len(text.split())
    ok = count <= int(param)
    return ok, f"Word count {count} {'≤' if ok else '>'} {param}"


@_rule("contains_sections")
def _contains_sections(text: str, sections: Any) -> tuple[bool, str]:
    missing = [s for s in sections if s.lower() not in text.lower()]
    if missing:
        return False, f"Missing sections: {', '.join(missing)}"
    return True, "All required sections present"


@_rule("no_placeholder")
def _no_placeholder(text: str, _: Any) -> tuple[bool, str]:
    placeholders = re.findall(r"\[.*?\]|\{.*?\}|<.*?>|TODO|FIXME|TBD", text)
    if placeholders:
        return False, f"Placeholders found: {placeholders[:5]}"
    return True, "No placeholders"


@_rule("min_sections")
def _min_sections_rule(text: str, param: Any) -> tuple[bool, str]:
    count = len(re.findall(r"^#+\s", text, re.MULTILINE))
    ok = count >= int(param)
    return ok, f"Section count {count} {'≥' if ok else '<'} {param}"


class RuleValidator:
    """Applies named rules to text artifacts."""

    def __init__(self, extra_rules_path: str | Path | None = None) -> None:
        self._rules = dict(_BUILTIN)
        if extra_rules_path:
            self._load_yaml_rules(Path(extra_rules_path))

    def _load_yaml_rules(self, path: Path) -> None:
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # YAML rules: name → {expr: "len(text) > 100", message: "..."}
        for name, cfg in data.get("rules", {}).items():
            expr = cfg.get("expr", "True")
            msg = cfg.get("message", f"Rule {name} failed")

            def _make_fn(e=expr, m=msg):
                def fn(text: str, _: Any) -> tuple[bool, str]:
                    try:
                        ok = bool(eval(e, {"text": text, "len": len, "re": re}))  # noqa: S307
                    except Exception:
                        ok = False
                    return ok, m if not ok else f"Rule {name} passed"
                return fn

            self._rules[name] = _make_fn()

    async def validate(self, content: str, rule: ValidationRule) -> DimensionScore:
        cfg = rule.config
        issues: list[ValidationIssue] = []
        total_weight = 0.0
        weighted_score = 0.0

        for rule_name, param in cfg.items():
            if rule_name not in self._rules:
                continue
            fn = self._rules[rule_name]
            passed, msg = fn(content, param)
            w = 1.0
            total_weight += w
            weighted_score += (100.0 if passed else 0.0) * w
            if not passed:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=msg,
                        dimension=rule_name,
                        suggestion=f"Fix rule: {rule_name}",
                    )
                )

        score = (weighted_score / total_weight) if total_weight > 0 else 100.0
        return DimensionScore(
            name=rule.name,
            score=score,
            weight=rule.weight,
            issues=issues,
        )
