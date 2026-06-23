"""Tests for prompt templates and store."""

from __future__ import annotations

import pytest
from pathlib import Path

from aeep.prompts.template import PromptTemplate, render_template
from aeep.prompts.store import PromptStore
from aeep.prompts.optimizer import PromptOptimizer


class TestRenderTemplate:
    def test_simple_variable(self):
        result = render_template("Hello, {{ name }}!", {"name": "World"})
        assert result == "Hello, World!"

    def test_conditional(self):
        src = "{% if show %}visible{% endif %}"
        assert render_template(src, {"show": True}) == "visible"
        assert render_template(src, {"show": False}) == ""

    def test_loop(self):
        src = "{% for item in items %}{{ item }} {% endfor %}"
        result = render_template(src, {"items": ["a", "b", "c"]})
        assert "a" in result and "b" in result and "c" in result

    def test_missing_variable_raises(self):
        from jinja2 import UndefinedError
        with pytest.raises(UndefinedError):
            render_template("{{ undefined_var }}", {})


class TestPromptTemplate:
    def test_render(self):
        tmpl = PromptTemplate(name="test", source="Task: {{ task }}")
        result = tmpl.render({"task": "write code"})
        assert result == "Task: write code"

    def test_version_increment(self):
        tmpl = PromptTemplate(name="test", source="v1", version=1)
        v2 = tmpl.with_source("v2")
        assert v2.version == 2
        assert v2.source == "v2"
        assert tmpl.source == "v1"  # original unchanged


class TestPromptStore:
    def test_load_builtin_templates(self):
        store = PromptStore()
        names = store.list_names()
        assert len(names) > 0
        assert any("architect" in n for n in names)

    def test_get_template(self):
        store = PromptStore()
        tmpl = store.get("system.architect")
        assert isinstance(tmpl, PromptTemplate)
        assert tmpl.source != ""

    def test_get_nonexistent_raises(self):
        store = PromptStore()
        with pytest.raises(KeyError):
            store.get("nonexistent.template")

    def test_put_and_get(self):
        store = PromptStore()
        tmpl = PromptTemplate(name="custom.test", source="Hello {{ name }}")
        store.put(tmpl)
        fetched = store.get("custom.test")
        assert fetched.source == "Hello {{ name }}"

    def test_render(self):
        store = PromptStore()
        store.put(PromptTemplate(name="greet", source="Hi {{ name }}"))
        result = store.render("greet", {"name": "Alice"})
        assert result == "Hi Alice"

    def test_versioning(self):
        store = PromptStore()
        v1 = PromptTemplate(name="versioned", source="v1", version=1)
        v2 = PromptTemplate(name="versioned", source="v2", version=2)
        store.put(v1)
        store.put(v2)
        assert store.get("versioned", version=1).source == "v1"
        assert store.get("versioned").source == "v2"  # latest


class TestPromptOptimizer:
    def test_best_returns_highest_score(self):
        opt = PromptOptimizer()
        t1 = PromptTemplate(name="q", source="v1", version=1)
        t2 = PromptTemplate(name="q", source="v2", version=2)
        opt.register(t1)
        opt.register(t2)
        opt.record_score("q", 1, 60.0)
        opt.record_score("q", 2, 90.0)
        best = opt.best("q")
        assert best is not None
        assert best.version == 2

    def test_empty_returns_none(self):
        opt = PromptOptimizer()
        assert opt.best("unknown") is None

    def test_ab_select_returns_template(self):
        opt = PromptOptimizer()
        t = PromptTemplate(name="ab", source="test")
        opt.register(t)
        opt.record_score("ab", 1, 75.0)
        selected = opt.ab_select("ab")
        assert selected is not None
