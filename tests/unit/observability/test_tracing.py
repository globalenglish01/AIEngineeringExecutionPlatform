"""Tests for lightweight span-based tracing."""

from __future__ import annotations

import pytest

from aeep.observability.tracing import Tracer, get_tracer, reset_tracer


@pytest.fixture(autouse=True)
def fresh_tracer():
    reset_tracer()
    yield
    reset_tracer()


class TestTracer:
    def test_span_created(self):
        t = Tracer()
        with t.start_span("test_op") as span:
            assert span.name == "test_op"
        assert len(t.get_spans()) == 1

    def test_span_has_duration(self):
        t = Tracer()
        with t.start_span("timed"):
            pass
        span = t.get_spans()[0]
        assert span.duration_ms >= 0

    def test_span_attributes(self):
        t = Tracer()
        with t.start_span("op", provider="openai", model="gpt-4o") as span:
            pass
        span = t.get_spans()[0]
        assert span.attributes["provider"] == "openai"

    def test_error_marks_span(self):
        t = Tracer()
        with pytest.raises(ValueError):
            with t.start_span("failing") as span:
                raise ValueError("oops")
        span = t.get_spans()[0]
        assert span.status == "ERROR"

    def test_nested_spans_parent_child(self):
        t = Tracer()
        with t.start_span("parent") as parent:
            with t.start_span("child") as child:
                pass
        spans = t.get_spans()
        assert len(spans) == 2
        child_span = next(s for s in spans if s.name == "child")
        assert child_span.parent_span_id == parent.span_id

    def test_same_trace_id_for_nested(self):
        t = Tracer()
        with t.start_span("root") as root:
            with t.start_span("leaf") as leaf:
                pass
        assert root.trace_id == leaf.trace_id

    def test_singleton(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2

    def test_clear(self):
        t = Tracer()
        with t.start_span("x"):
            pass
        t.clear()
        assert t.get_spans() == []
