"""Tests for the DAG engine."""

from __future__ import annotations

from typing import Any

import pytest

from aeep.workflow.dag import CycleDetectedError, DAG, DAGNode


class _EchoNode(DAGNode):
    """Test node that writes a value into context."""

    def __init__(self, node_id: str, value: str, depends_on: list[str] | None = None) -> None:
        super().__init__(node_id=node_id, node_type="echo", depends_on=depends_on)
        self.value = value
        self.executed = False

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        self.executed = True
        return {self.node_id: self.value}


class _FailNode(DAGNode):
    def __init__(self, node_id: str) -> None:
        super().__init__(node_id=node_id, node_type="fail")

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("intentional failure")


class TestDAGTopology:
    def test_empty_dag_returns_empty_levels(self):
        dag = DAG()
        assert dag.topological_order() == []

    def test_single_node(self):
        dag = DAG()
        dag.add_node(_EchoNode("a", "hello"))
        levels = dag.topological_order()
        assert len(levels) == 1
        assert levels[0] == ["a"]

    def test_linear_chain(self):
        dag = DAG()
        dag.add_node(_EchoNode("a", "1"))
        dag.add_node(_EchoNode("b", "2", depends_on=["a"]))
        dag.add_node(_EchoNode("c", "3", depends_on=["b"]))
        levels = dag.topological_order()
        assert len(levels) == 3
        assert levels[0] == ["a"]
        assert levels[1] == ["b"]
        assert levels[2] == ["c"]

    def test_parallel_nodes_in_same_level(self):
        dag = DAG()
        dag.add_node(_EchoNode("root", "r"))
        dag.add_node(_EchoNode("child1", "c1", depends_on=["root"]))
        dag.add_node(_EchoNode("child2", "c2", depends_on=["root"]))
        levels = dag.topological_order()
        assert len(levels) == 2
        assert set(levels[1]) == {"child1", "child2"}

    def test_duplicate_node_raises(self):
        dag = DAG()
        dag.add_node(_EchoNode("a", "1"))
        with pytest.raises(ValueError, match="Duplicate node id"):
            dag.add_node(_EchoNode("a", "2"))

    def test_unknown_dependency_raises(self):
        dag = DAG()
        dag.add_node(_EchoNode("b", "2", depends_on=["nonexistent"]))
        with pytest.raises(ValueError, match="unknown"):
            dag.topological_order()

    def test_cycle_detected(self):
        dag = DAG()
        dag.add_node(_EchoNode("a", "1", depends_on=["b"]))
        dag.add_node(_EchoNode("b", "2", depends_on=["a"]))
        with pytest.raises(CycleDetectedError):
            dag.topological_order()


class TestDAGExecution:
    @pytest.mark.asyncio
    async def test_linear_execution_order(self):
        order: list[str] = []

        class _OrderNode(DAGNode):
            def __init__(self, nid: str, deps: list[str] | None = None):
                super().__init__(node_id=nid, node_type="order", depends_on=deps)

            async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
                order.append(self.node_id)
                return {self.node_id: True}

        dag = DAG()
        dag.add_node(_OrderNode("a"))
        dag.add_node(_OrderNode("b", deps=["a"]))
        dag.add_node(_OrderNode("c", deps=["b"]))
        await dag.execute({})
        assert order == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_context_propagation(self):
        dag = DAG()
        dag.add_node(_EchoNode("step1", "hello"))
        dag.add_node(_EchoNode("step2", "world", depends_on=["step1"]))
        ctx = await dag.execute({})
        assert ctx["step1"] == "hello"
        assert ctx["step2"] == "world"

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        import asyncio

        started_at: dict[str, float] = {}

        class _SlowNode(DAGNode):
            def __init__(self, nid: str):
                super().__init__(node_id=nid, node_type="slow")

            async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
                import time
                started_at[self.node_id] = time.monotonic()
                await asyncio.sleep(0.05)
                return {self.node_id: True}

        dag = DAG()
        dag.add_node(_SlowNode("a"))
        dag.add_node(_SlowNode("b"))  # independent of a
        dag.add_node(_EchoNode("c", "done", depends_on=["a", "b"]))
        await dag.execute({})
        # a and b should start at roughly the same time (within 20ms)
        assert abs(started_at["a"] - started_at["b"]) < 0.03

    @pytest.mark.asyncio
    async def test_resume_skips_completed(self):
        executed: set[str] = set()

        class _TrackNode(DAGNode):
            async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
                executed.add(self.node_id)
                return {self.node_id: True}

        dag = DAG()
        dag.add_node(_TrackNode("a", "track"))
        dag.add_node(_TrackNode("b", "track", depends_on=["a"]))
        dag.add_node(_TrackNode("c", "track", depends_on=["b"]))

        # Simulate "a" already done
        await dag.execute({}, completed_nodes={"a"})
        assert "a" not in executed
        assert "b" in executed
        assert "c" in executed

    @pytest.mark.asyncio
    async def test_failure_propagates(self):
        dag = DAG()
        dag.add_node(_FailNode("boom"))
        with pytest.raises(RuntimeError, match="intentional failure"):
            await dag.execute({})

    @pytest.mark.asyncio
    async def test_on_node_callbacks(self):
        started: list[str] = []
        done: list[str] = []

        async def _on_start(nid: str) -> None:
            started.append(nid)

        async def _on_done(nid: str, output: Any) -> None:
            done.append(nid)

        dag = DAG()
        dag.add_node(_EchoNode("x", "val"))
        await dag.execute({}, on_node_start=_on_start, on_node_done=_on_done)
        assert "x" in started
        assert "x" in done
