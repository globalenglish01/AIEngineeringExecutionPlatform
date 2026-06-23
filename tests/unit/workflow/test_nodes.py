"""Tests for individual workflow node types."""

from __future__ import annotations

from typing import Any

import pytest

from aeep.workflow.nodes.branch_node import BranchNode
from aeep.workflow.nodes.code_execution_node import CodeExecutionNode
from aeep.workflow.nodes.loop_node import LoopNode
from aeep.workflow.nodes.parallel_node import ParallelNode
from aeep.workflow.nodes.validation_node import ValidationNode


class TestBranchNode:
    @pytest.mark.asyncio
    async def test_truthy_true(self):
        node = BranchNode(
            "b1",
            config={"condition_key": "flag", "condition_op": "truthy",
                    "true_branch": "yes", "false_branch": "no"},
        )
        out = await node.execute({"flag": True})
        assert out["b1"] == "yes"

    @pytest.mark.asyncio
    async def test_truthy_false(self):
        node = BranchNode(
            "b2",
            config={"condition_key": "flag", "condition_op": "truthy",
                    "true_branch": "yes", "false_branch": "no"},
        )
        out = await node.execute({"flag": False})
        assert out["b2"] == "no"

    @pytest.mark.asyncio
    async def test_eq_operator(self):
        node = BranchNode(
            "b3",
            config={"condition_key": "val", "condition_op": "eq",
                    "condition_value": 42, "true_branch": "hit", "false_branch": "miss"},
        )
        out = await node.execute({"val": 42})
        assert out["b3"] == "hit"

    @pytest.mark.asyncio
    async def test_gt_operator(self):
        node = BranchNode(
            "b4",
            config={"condition_key": "score", "condition_op": "gt",
                    "condition_value": 70, "true_branch": "pass", "false_branch": "fail"},
        )
        out = await node.execute({"score": 85})
        assert out["b4"] == "pass"

    @pytest.mark.asyncio
    async def test_contains_operator(self):
        node = BranchNode(
            "b5",
            config={"condition_key": "text", "condition_op": "contains",
                    "condition_value": "hello", "true_branch": "found", "false_branch": "not_found"},
        )
        out = await node.execute({"text": "say hello world"})
        assert out["b5"] == "found"

    @pytest.mark.asyncio
    async def test_unknown_op_raises(self):
        node = BranchNode("b6", config={"condition_key": "x", "condition_op": "bad_op"})
        with pytest.raises(ValueError):
            await node.execute({"x": 1})


class TestCodeExecutionNode:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        node = CodeExecutionNode(
            "exec1",
            config={"code_key": "code", "timeout": 10},
        )
        ctx = {"code": "print('hello world')"}
        out = await node.execute(ctx)
        assert out["exec1"]["exit_code"] == 0
        assert "hello world" in out["exec1"]["stdout"]

    @pytest.mark.asyncio
    async def test_syntax_error_captured(self):
        node = CodeExecutionNode("exec2", config={"code_key": "code"})
        out = await node.execute({"code": "def bad syntax here$$"})
        assert out["exec2"]["exit_code"] != 0
        assert out["exec2"]["stderr"] != ""

    @pytest.mark.asyncio
    async def test_empty_code(self):
        node = CodeExecutionNode("exec3", config={"code_key": "code"})
        out = await node.execute({"code": ""})
        assert out["exec3"]["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        node = CodeExecutionNode(
            "exec4",
            config={"code_key": "code", "timeout": 1},
        )
        out = await node.execute({"code": "import time; time.sleep(10)"})
        assert out["exec4"]["exit_code"] == -1
        assert "timed out" in out["exec4"]["stderr"].lower()


class TestValidationNode:
    @pytest.mark.asyncio
    async def test_pass_on_long_content(self):
        node = ValidationNode(
            "val1",
            config={"input_key": "content", "min_score": 60.0, "on_fail": "warn"},
        )
        long_text = "word " * 300  # 300 words -> score ~65
        out = await node.execute({"content": long_text})
        assert out["val1_passed"] is True

    @pytest.mark.asyncio
    async def test_fail_on_empty_content(self):
        node = ValidationNode(
            "val2",
            config={"input_key": "content", "min_score": 70.0, "on_fail": "raise"},
        )
        from aeep.core.exceptions import QualityGateFailedError
        with pytest.raises(QualityGateFailedError):
            await node.execute({"content": ""})

    @pytest.mark.asyncio
    async def test_warn_on_fail(self):
        node = ValidationNode(
            "val3",
            config={"input_key": "content", "min_score": 70.0, "on_fail": "warn"},
        )
        # Short content gets low score but doesn't raise
        out = await node.execute({"content": "short"})
        assert "val3_score" in out


class TestLoopNode:
    @pytest.mark.asyncio
    async def test_exits_when_condition_met(self):
        from aeep.workflow.nodes.base import BaseNode

        class _SetPassNode(BaseNode):
            node_type = "set_pass"
            async def execute(self, ctx: dict) -> dict:
                return {"my_validation_passed": True}

        inner = _SetPassNode("inner")
        node = LoopNode(
            "loop1",
            inner_nodes=[inner],
            config={"max_iterations": 5, "exit_key": "my_validation_passed"},
        )
        out = await node.execute({})
        assert out["loop1"]["iterations"] == 1
        assert out["loop1"]["exit_reason"] == "condition_met"

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self):
        from aeep.workflow.nodes.base import BaseNode

        class _NeverPassNode(BaseNode):
            node_type = "never"
            async def execute(self, ctx: dict) -> dict:
                return {}

        node = LoopNode(
            "loop2",
            inner_nodes=[_NeverPassNode("inner")],
            config={"max_iterations": 3, "exit_key": "never_set"},
        )
        out = await node.execute({})
        assert out["loop2"]["iterations"] == 3
        assert out["loop2"]["exit_reason"] == "max_iterations"


class TestParallelNode:
    @pytest.mark.asyncio
    async def test_parallel_results_merged(self):
        from aeep.workflow.nodes.base import BaseNode

        class _ValNode(BaseNode):
            node_type = "val"
            def __init__(self, nid: str, val: str):
                super().__init__(nid)
                self._val = val
            async def execute(self, ctx: dict) -> dict:
                return {self.node_id: self._val}

        node = ParallelNode(
            "par1",
            inner_nodes=[_ValNode("a", "alpha"), _ValNode("b", "beta")],
        )
        out = await node.execute({})
        assert out["a"] == "alpha"
        assert out["b"] == "beta"
        assert len(out["par1"]) == 2

    @pytest.mark.asyncio
    async def test_partial_failure_non_fatal(self):
        from aeep.workflow.nodes.base import BaseNode

        class _FailNode(BaseNode):
            node_type = "fail"
            async def execute(self, ctx: dict) -> dict:
                raise RuntimeError("boom")

        class _OkNode(BaseNode):
            node_type = "ok"
            async def execute(self, ctx: dict) -> dict:
                return {"ok": True}

        node = ParallelNode(
            "par2",
            inner_nodes=[_FailNode("f"), _OkNode("o")],
            config={"fail_fast": False},
        )
        out = await node.execute({})
        assert "par2_errors" in out
        assert out["ok"] is True
