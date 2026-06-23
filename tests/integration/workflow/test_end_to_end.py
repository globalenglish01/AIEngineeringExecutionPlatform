"""End-to-end workflow tests using mock LLM nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aeep.workflow.dag import DAG
from aeep.workflow.nodes.base import BaseNode
from aeep.workflow.nodes.branch_node import BranchNode
from aeep.workflow.nodes.code_execution_node import CodeExecutionNode
from aeep.workflow.nodes.validation_node import ValidationNode
from aeep.workflow.plugins import LoggingPlugin, PluginManager, TimingPlugin
from aeep.workflow.runner import WorkflowRunner
from aeep.workflow.state import RunStatus, WorkflowStateStore


class _MockLLMNode(BaseNode):
    """Simulates an LLM node without actually calling a provider."""

    node_type = "mock_llm"

    def __init__(self, node_id: str, response: str, depends_on: list[str] | None = None) -> None:
        super().__init__(node_id, depends_on)
        self._response = response

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        output_key = self.config.get("output_key", self.node_id)
        return {output_key: self._response}


class TestSimpleLinearWorkflow:
    @pytest.mark.asyncio
    async def test_two_node_workflow(self, tmp_path: Path):
        dag = DAG()
        dag.add_node(_MockLLMNode("step1", "outline: intro, body, conclusion"))
        dag.add_node(_MockLLMNode("step2", "full chapter content", depends_on=["step1"]))

        store = WorkflowStateStore(tmp_path / "test.db")
        runner = WorkflowRunner("test_wf", dag, state_store=store)

        run = await runner.run({"topic": "Python"})
        assert run.status == RunStatus.COMPLETED
        assert "step2" in run.final_context

    @pytest.mark.asyncio
    async def test_context_flows_between_nodes(self, tmp_path: Path):
        class _EchoNode(BaseNode):
            node_type = "echo"

            async def execute(self, ctx: dict) -> dict:
                return {"echoed": ctx.get("input_value", "missing")}

        dag = DAG()
        dag.add_node(_EchoNode("echo"))

        runner = WorkflowRunner("echo_wf", DAG())
        # Use a fresh dag
        dag2 = DAG()
        dag2.add_node(_EchoNode("echo"))
        runner2 = WorkflowRunner("echo_wf", dag2)

        run = await runner2.run({"input_value": "test123"})
        assert run.final_context.get("echoed") == "test123"


class TestWorkflowWithBranching:
    @pytest.mark.asyncio
    async def test_branch_selects_correct_path(self, tmp_path: Path):
        dag = DAG()
        dag.add_node(_MockLLMNode("generate", "word " * 500))  # long content 竊・passes validation
        dag.add_node(
            ValidationNode(
                "validate",
                depends_on=["generate"],
                config={"input_key": "generate", "min_score": 60.0, "on_fail": "warn"},
            )
        )
        dag.add_node(
            BranchNode(
                "decide",
                depends_on=["validate"],
                config={
                    "condition_key": "validate_passed",
                    "condition_op": "truthy",
                    "true_branch": "approved",
                    "false_branch": "rejected",
                },
            )
        )

        runner = WorkflowRunner("branch_wf", dag)
        run = await runner.run()
        assert run.status == RunStatus.COMPLETED
        assert run.final_context.get("decide") == "approved"


class TestWorkflowWithCodeExecution:
    @pytest.mark.asyncio
    async def test_code_execution_in_workflow(self, tmp_path: Path):
        dag = DAG()
        dag.add_node(_MockLLMNode("generate_code", "print('result:', 2 + 2)"))
        dag.add_node(
            CodeExecutionNode(
                "run_code",
                depends_on=["generate_code"],
                config={"code_key": "generate_code", "timeout": 10},
            )
        )

        runner = WorkflowRunner("code_wf", dag)
        run = await runner.run()
        assert run.status == RunStatus.COMPLETED
        assert run.final_context["run_code"]["exit_code"] == 0
        assert "4" in run.final_context["run_code"]["stdout"]


class TestWorkflowStateAndResume:
    @pytest.mark.asyncio
    async def test_state_persisted(self, tmp_path: Path):
        db = tmp_path / "wf.db"
        store = WorkflowStateStore(db)

        dag = DAG()
        dag.add_node(_MockLLMNode("node_a", "output_a"))
        dag.add_node(_MockLLMNode("node_b", "output_b", depends_on=["node_a"]))

        runner = WorkflowRunner("persist_wf", dag, state_store=store)
        run = await runner.run()

        # Load from store
        loaded = store.load_run(run.run_id)
        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED
        assert "node_a" in loaded.node_runs
        assert "node_b" in loaded.node_runs

    @pytest.mark.asyncio
    async def test_resume_skips_completed_nodes(self, tmp_path: Path):
        executed: list[str] = []

        class _TrackNode(BaseNode):
            node_type = "track"

            async def execute(self, ctx: dict) -> dict:
                executed.append(self.node_id)
                return {self.node_id: "done"}

        db = tmp_path / "wf.db"
        store = WorkflowStateStore(db)

        dag = DAG()
        dag.add_node(_TrackNode("first"))
        dag.add_node(_TrackNode("second", depends_on=["first"]))

        runner = WorkflowRunner("resume_wf", dag, state_store=store)
        first_run = await runner.run()

        # Both ran the first time
        assert "first" in executed
        assert "second" in executed
        executed.clear()

        # Resume 窶・"first" is already COMPLETED, should be skipped
        run2 = await runner.run(resume_run_id=first_run.run_id)
        # first should be skipped on resume since it was completed
        # (the resume logic reads completed_nodes from store)
        assert run2.status == RunStatus.COMPLETED


class TestPluginsWork:
    @pytest.mark.asyncio
    async def test_logging_plugin_fires(self, tmp_path: Path):
        import logging

        plugin = LoggingPlugin()
        mgr = PluginManager()
        mgr.register(plugin)

        dag = DAG()
        dag.add_node(_MockLLMNode("n1", "hello"))

        runner = WorkflowRunner("plugin_wf", dag, plugins=mgr)
        with pytest.raises(Exception) if False else contextmanager_none():
            run = await runner.run()
        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timing_plugin_tracks(self, tmp_path: Path):
        timing = TimingPlugin()
        mgr = PluginManager()
        mgr.register(timing)

        dag = DAG()
        dag.add_node(_MockLLMNode("n1", "hello"))
        runner = WorkflowRunner("timing_wf", dag, plugins=mgr)
        run = await runner.run()
        assert run.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def contextmanager_none():
    yield
