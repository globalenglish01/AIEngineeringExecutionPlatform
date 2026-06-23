"""Tests for in-process metrics registry."""

from __future__ import annotations

import pytest

from aeep.observability.metrics import MetricsRegistry, get_metrics, reset_metrics


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_metrics()
    yield
    reset_metrics()


class TestMetricsRegistry:
    def test_counter_inc(self):
        reg = MetricsRegistry()
        c = reg.counter("test_counter", {"env": "test"})
        c.inc(3.0)
        assert c.value == 3.0

    def test_counter_same_labels_same_instance(self):
        reg = MetricsRegistry()
        c1 = reg.counter("my_counter", {"k": "v"})
        c2 = reg.counter("my_counter", {"k": "v"})
        c1.inc(5)
        assert c2.value == 5.0

    def test_histogram_observe(self):
        reg = MetricsRegistry()
        h = reg.histogram("latency", {"op": "read"})
        h.observe(0.1)
        h.observe(0.2)
        assert h.count == 2
        assert abs(h.mean - 0.15) < 1e-9

    def test_record_workflow_run(self):
        reg = MetricsRegistry()
        reg.record_workflow_run("my_wf", 1.5, success=True)
        snap = reg.snapshot()
        assert any("workflow_run_total" in k for k in snap["counters"])

    def test_record_llm_call(self):
        reg = MetricsRegistry()
        reg.record_llm_call("openai", "gpt-4o", 0.002, 0.5)
        snap = reg.snapshot()
        assert any("llm_call_total" in k for k in snap["counters"])
        assert any("llm_cost_usd_total" in k for k in snap["counters"])

    def test_record_validation_score(self):
        reg = MetricsRegistry()
        reg.record_validation_score("document", 85.0)
        snap = reg.snapshot()
        assert any("validation_score" in k for k in snap["histograms"])

    def test_snapshot_structure(self):
        reg = MetricsRegistry()
        reg.counter("a").inc()
        reg.histogram("b").observe(1.0)
        snap = reg.snapshot()
        assert "counters" in snap
        assert "histograms" in snap

    def test_singleton(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2
