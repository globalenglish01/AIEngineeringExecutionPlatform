"""Tests for WorkflowStateStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeep.core.interfaces.workflow import NodeStatus
from aeep.workflow.state import NodeRun, RunStatus, WorkflowRun, WorkflowStateStore


class TestWorkflowStateStore:
    def test_create_and_load_run(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        run = WorkflowRun(workflow_name="test_wf")
        store.create_run(run)

        loaded = store.load_run(run.run_id)
        assert loaded is not None
        assert loaded.workflow_name == "test_wf"
        assert loaded.status == RunStatus.PENDING

    def test_update_run_status(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        run = WorkflowRun(workflow_name="test_wf")
        store.create_run(run)
        run.status = RunStatus.COMPLETED
        store.update_run(run)

        loaded = store.load_run(run.run_id)
        assert loaded.status == RunStatus.COMPLETED

    def test_upsert_node_run(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        run = WorkflowRun(workflow_name="test_wf")
        store.create_run(run)

        nr = NodeRun(node_id="n1", run_id=run.run_id, status=NodeStatus.COMPLETED,
                     output={"result": "ok"})
        store.upsert_node_run(nr)

        loaded = store.load_run(run.run_id)
        assert "n1" in loaded.node_runs
        assert loaded.node_runs["n1"].status == NodeStatus.COMPLETED

    def test_completed_nodes(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        run = WorkflowRun(workflow_name="test_wf")
        store.create_run(run)

        for nid, status in [("a", NodeStatus.COMPLETED), ("b", NodeStatus.FAILED)]:
            nr = NodeRun(node_id=nid, run_id=run.run_id, status=status)
            store.upsert_node_run(nr)

        loaded = store.load_run(run.run_id)
        assert loaded.completed_nodes() == {"a"}

    def test_list_runs(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        for i in range(3):
            run = WorkflowRun(workflow_name="my_wf")
            store.create_run(run)

        runs = store.list_runs("my_wf")
        assert len(runs) == 3

    def test_load_nonexistent_run(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        assert store.load_run("nonexistent-id") is None

    def test_schema_idempotent(self, tmp_path: Path):
        db = tmp_path / "test.db"
        WorkflowStateStore(db)
        WorkflowStateStore(db)  # should not raise

    def test_initial_context_persisted(self, tmp_path: Path):
        store = WorkflowStateStore(tmp_path / "test.db")
        run = WorkflowRun(workflow_name="ctx_wf", initial_context={"key": "value"})
        store.create_run(run)

        loaded = store.load_run(run.run_id)
        assert loaded.initial_context.get("key") == "value"
