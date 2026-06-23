"""Unit tests for individual validators."""

from __future__ import annotations

import pytest

from aeep.validation.models import RuleType, Severity, ValidationRule
from aeep.validation.validators.code_validator import CodeValidator
from aeep.validation.validators.consistency_validator import ConsistencyValidator
from aeep.validation.validators.rule_validator import RuleValidator
from aeep.validation.validators.schema_validator import SchemaValidator


class TestSchemaValidator:
    @pytest.mark.asyncio
    async def test_valid_json_schema(self):
        v = SchemaValidator()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        rule = ValidationRule("schema_check", RuleType.SCHEMA, config={"json_schema": schema})
        import json
        result = await v.validate(json.dumps({"name": "Alice"}), rule)
        assert result.score == 100.0
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_invalid_json_schema(self):
        v = SchemaValidator()
        schema = {"type": "object", "required": ["name"]}
        rule = ValidationRule("schema_check", RuleType.SCHEMA, config={"json_schema": schema})
        import json
        result = await v.validate(json.dumps({"age": 30}), rule)
        assert result.score == 0.0
        assert any(i.severity == Severity.ERROR for i in result.issues)

    @pytest.mark.asyncio
    async def test_text_min_words(self):
        v = SchemaValidator()
        rule = ValidationRule("text_check", RuleType.SCHEMA, config={"min_words": 100})
        result = await v.validate("short text", rule)
        assert result.score < 100.0
        assert any("Too short" in i.message for i in result.issues)

    @pytest.mark.asyncio
    async def test_text_passes_word_count(self):
        v = SchemaValidator()
        rule = ValidationRule("text_check", RuleType.SCHEMA, config={"min_words": 5})
        result = await v.validate("this text has enough words here", rule)
        assert result.score == 100.0


class TestRuleValidator:
    @pytest.mark.asyncio
    async def test_min_words_passes(self):
        v = RuleValidator()
        rule = ValidationRule("rule_check", RuleType.RULE, config={"min_words": 5})
        result = await v.validate("one two three four five six", rule)
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_min_words_fails(self):
        v = RuleValidator()
        rule = ValidationRule("rule_check", RuleType.RULE, config={"min_words": 100})
        result = await v.validate("too short", rule)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_contains_sections(self):
        v = RuleValidator()
        rule = ValidationRule("sections", RuleType.RULE,
                              config={"contains_sections": ["Introduction", "Conclusion"]})
        text = "## Introduction\nSome text.\n## Conclusion\nEnd."
        result = await v.validate(text, rule)
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_no_placeholder_fails(self):
        v = RuleValidator()
        rule = ValidationRule("clean", RuleType.RULE, config={"no_placeholder": None})
        result = await v.validate("Content with [TODO] here", rule)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_no_placeholder_passes(self):
        v = RuleValidator()
        rule = ValidationRule("clean", RuleType.RULE, config={"no_placeholder": None})
        result = await v.validate("Clean content without any placeholders", rule)
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_max_words_passes(self):
        v = RuleValidator()
        rule = ValidationRule("length", RuleType.RULE, config={"max_words": 100})
        result = await v.validate("short", rule)
        assert result.score == 100.0


class TestCodeValidator:
    @pytest.mark.asyncio
    async def test_valid_syntax(self):
        v = CodeValidator()
        rule = ValidationRule("syntax", RuleType.CODE, config={"checks": ["syntax"]})
        result = await v.validate("def foo():\n    return 42\n", rule)
        assert result.score == 100.0
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_invalid_syntax(self):
        v = CodeValidator()
        rule = ValidationRule("syntax", RuleType.CODE, config={"checks": ["syntax"]})
        result = await v.validate("def bad syntax$$", rule)
        assert result.score < 100.0
        assert any(i.severity == Severity.ERROR for i in result.issues)

    @pytest.mark.asyncio
    async def test_unsupported_language(self):
        v = CodeValidator()
        rule = ValidationRule("js", RuleType.CODE,
                              config={"language": "javascript", "checks": ["syntax"]})
        result = await v.validate("const x = 1;", rule)
        assert any(i.severity == Severity.INFO for i in result.issues)


class TestConsistencyValidator:
    @pytest.mark.asyncio
    async def test_term_inconsistency_detected(self):
        v = ConsistencyValidator()
        rule = ValidationRule("consistency", RuleType.CONSISTENCY,
                              config={"term_map": {"async/await": ["async-await", "asyncawait"]}})
        result = await v.validate("Use async-await pattern here", rule)
        assert any("async-await" in i.message for i in result.issues)

    @pytest.mark.asyncio
    async def test_no_issues(self):
        v = ConsistencyValidator()
        rule = ValidationRule("consistency", RuleType.CONSISTENCY, config={})
        result = await v.validate("Clean consistent text with no issues", rule)
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_duplicate_headings(self):
        v = ConsistencyValidator()
        rule = ValidationRule("consistency", RuleType.CONSISTENCY, config={})
        text = "## Introduction\nText\n## Introduction\nMore text"
        result = await v.validate(text, rule)
        assert any("Duplicate" in i.message for i in result.issues)
