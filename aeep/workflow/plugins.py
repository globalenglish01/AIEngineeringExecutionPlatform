"""Plugin hook system for workflow lifecycle events."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowPlugin(ABC):
    """Base class for all workflow plugins."""

    name: str = "base"

    async def on_run_start(self, run_id: str, context: dict[str, Any]) -> None:
        pass

    async def on_run_end(self, run_id: str, context: dict[str, Any], error: Exception | None) -> None:
        pass

    async def on_node_start(self, run_id: str, node_id: str, context: dict[str, Any]) -> None:
        pass

    async def on_node_end(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any] | None,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        pass


class PluginManager:
    """Manages ordered plugin list and dispatches events."""

    def __init__(self) -> None:
        self._plugins: list[WorkflowPlugin] = []

    def register(self, plugin: WorkflowPlugin) -> None:
        self._plugins.append(plugin)
        logger.debug("Plugin '%s' registered", plugin.name)

    async def run_start(self, run_id: str, context: dict[str, Any]) -> None:
        for p in self._plugins:
            try:
                await p.on_run_start(run_id, context)
            except Exception as exc:
                logger.error("Plugin '%s' on_run_start error: %s", p.name, exc)

    async def run_end(self, run_id: str, context: dict[str, Any], error: Exception | None) -> None:
        for p in self._plugins:
            try:
                await p.on_run_end(run_id, context, error)
            except Exception as exc:
                logger.error("Plugin '%s' on_run_end error: %s", p.name, exc)

    async def node_start(self, run_id: str, node_id: str, context: dict[str, Any]) -> None:
        for p in self._plugins:
            try:
                await p.on_node_start(run_id, node_id, context)
            except Exception as exc:
                logger.error("Plugin '%s' on_node_start error: %s", p.name, exc)

    async def node_end(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any] | None,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        for p in self._plugins:
            try:
                await p.on_node_end(run_id, node_id, output, duration_ms, error)
            except Exception as exc:
                logger.error("Plugin '%s' on_node_end error: %s", p.name, exc)


# ---------------------------------------------------------------------------
# Built-in plugins
# ---------------------------------------------------------------------------


class LoggingPlugin(WorkflowPlugin):
    """Emits structured log entries for run and node lifecycle events."""

    name = "logging"

    async def on_run_start(self, run_id: str, context: dict[str, Any]) -> None:
        logger.info("workflow_run_start run_id=%s", run_id)

    async def on_run_end(self, run_id: str, context: dict[str, Any], error: Exception | None) -> None:
        if error:
            logger.error("workflow_run_failed run_id=%s error=%s", run_id, error)
        else:
            logger.info("workflow_run_completed run_id=%s", run_id)

    async def on_node_end(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any] | None,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        if error:
            logger.warning(
                "node_failed run_id=%s node_id=%s duration_ms=%d error=%s",
                run_id, node_id, duration_ms, error,
            )
        else:
            logger.info(
                "node_completed run_id=%s node_id=%s duration_ms=%d",
                run_id, node_id, duration_ms,
            )


class CostTrackingPlugin(WorkflowPlugin):
    """Records per-node LLM cost from CompletionResult stored in context."""

    name = "cost_tracking"

    def __init__(self, cost_tracker: Any) -> None:
        self._tracker = cost_tracker

    async def on_node_end(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any] | None,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        if not output or error:
            return
        # LLMNode stores CompletionResult at key f"{node_id}_result"
        result = output.get(f"{node_id}_result")
        if result is None:
            return
        from aeep.providers.cost_tracker import CostRecord

        record = CostRecord(
            provider_name=result.provider_name,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=0.0,  # actual cost computed by Provider
            duration_ms=result.duration_ms,
            run_id=run_id,
        )
        self._tracker.record(record)


class TimingPlugin(WorkflowPlugin):
    """Tracks per-node wall-clock time and stores in context."""

    name = "timing"

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}

    async def on_node_start(self, run_id: str, node_id: str, context: dict[str, Any]) -> None:
        self._start_times[f"{run_id}:{node_id}"] = time.monotonic()

    async def on_node_end(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any] | None,
        duration_ms: int,
        error: Exception | None,
    ) -> None:
        key = f"{run_id}:{node_id}"
        self._start_times.pop(key, None)
