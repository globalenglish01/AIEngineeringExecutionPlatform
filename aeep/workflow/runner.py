"""WorkflowRunner — orchestrates DAG execution with state persistence and plugins."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from aeep.core.interfaces.workflow import NodeStatus
from aeep.workflow.dag import DAG
from aeep.workflow.plugins import PluginManager
from aeep.workflow.state import NodeRun, RunStatus, WorkflowRun, WorkflowStateStore

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """Ties together DAG, state store, and plugins for a single workflow execution."""

    def __init__(
        self,
        workflow_name: str,
        dag: DAG,
        state_store: WorkflowStateStore | None = None,
        plugins: PluginManager | None = None,
    ) -> None:
        self._name = workflow_name
        self._dag = dag
        self._store = state_store
        self._plugins = plugins or PluginManager()

    async def run(
        self,
        initial_context: dict[str, Any] | None = None,
        resume_run_id: str | None = None,
    ) -> WorkflowRun:
        """Execute the workflow.

        If *resume_run_id* is given, loads that run from the store and skips
        already-completed nodes (checkpoint resume).
        """
        context = dict(initial_context or {})

        if resume_run_id and self._store:
            existing = self._store.load_run(resume_run_id)
            if existing:
                run = existing
                run.status = RunStatus.RUNNING
                context.update(existing.final_context)
                logger.info("Resuming run '%s' (%d nodes already done)", run.run_id, len(run.completed_nodes()))
            else:
                run = self._new_run(context)
        else:
            run = self._new_run(context)

        if self._store:
            self._store.create_run(run) if not resume_run_id else self._store.update_run(run)

        await self._plugins.run_start(run.run_id, context)
        run_error: Exception | None = None

        async def _on_node_start(node_id: str) -> None:
            nr = NodeRun(node_id=node_id, run_id=run.run_id, status=NodeStatus.RUNNING,
                         started_at=datetime.now(UTC))
            run.node_runs[node_id] = nr
            if self._store:
                self._store.upsert_node_run(nr)
            await self._plugins.node_start(run.run_id, node_id, context)

        async def _on_node_done(node_id: str, output: dict | None) -> None:
            nr = run.node_runs.get(node_id, NodeRun(node_id=node_id, run_id=run.run_id))
            nr.status = NodeStatus.COMPLETED
            nr.completed_at = datetime.now(UTC)
            nr.output = output or {}
            if self._store:
                self._store.upsert_node_run(nr)
            duration_ms = nr.duration_ms or 0
            await self._plugins.node_end(run.run_id, node_id, output, duration_ms, None)

        async def _on_node_error(node_id: str, exc: Exception) -> None:
            nr = run.node_runs.get(node_id, NodeRun(node_id=node_id, run_id=run.run_id))
            nr.status = NodeStatus.FAILED
            nr.completed_at = datetime.now(UTC)
            nr.error = str(exc)
            if self._store:
                self._store.upsert_node_run(nr)
            await self._plugins.node_end(run.run_id, node_id, None, 0, exc)

        try:
            await self._dag.execute(
                context,
                completed_nodes=run.completed_nodes(),
                on_node_start=_on_node_start,
                on_node_done=_on_node_done,
                on_node_error=_on_node_error,
            )
            run.status = RunStatus.COMPLETED
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run_error = exc
            logger.error("WorkflowRun '%s' failed: %s", run.run_id, exc)
        finally:
            run.completed_at = datetime.now(UTC)
            run.final_context = context
            if self._store:
                self._store.update_run(run)

        await self._plugins.run_end(run.run_id, context, run_error)
        return run

    def _new_run(self, context: dict[str, Any]) -> WorkflowRun:
        return WorkflowRun(
            workflow_name=self._name,
            initial_context=dict(context),
        )
