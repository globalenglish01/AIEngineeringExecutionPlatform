"""Alerting — quality-gate failures, provider failures, budget overruns."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    severity: AlertSeverity
    title: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class AlertChannel:
    """Base class for alert delivery channels."""

    async def send(self, alert: Alert) -> None:
        raise NotImplementedError


class ConsoleAlertChannel(AlertChannel):
    """Prints alerts to stdout/stderr."""

    async def send(self, alert: Alert) -> None:
        icon = {"info": "ℹ", "warning": "⚠", "critical": "🚨"}.get(alert.severity.value, "•")
        print(f"{icon} [{alert.severity.value.upper()}] {alert.title}: {alert.message}")


class FileAlertChannel(AlertChannel):
    """Appends alerts to a JSONL log file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def send(self, alert: Alert) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": alert.timestamp,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "metadata": alert.metadata,
            }) + "\n")


class AlertManager:
    """Routes alerts to configured channels."""

    def __init__(self, channels: list[AlertChannel] | None = None) -> None:
        self._channels: list[AlertChannel] = channels or [ConsoleAlertChannel()]
        self._history: list[Alert] = []

    def add_channel(self, channel: AlertChannel) -> None:
        self._channels.append(channel)

    async def alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        **metadata: Any,
    ) -> None:
        a = Alert(severity=severity, title=title, message=message, metadata=metadata)
        self._history.append(a)
        for ch in self._channels:
            try:
                await ch.send(a)
            except Exception:
                pass

    async def quality_gate_failed(self, artifact_id: str, score: float, threshold: float) -> None:
        await self.alert(
            title="Quality Gate Failed",
            message=f"Artifact {artifact_id!r}: score {score:.1f} < {threshold:.1f}",
            severity=AlertSeverity.WARNING,
            artifact_id=artifact_id, score=score, threshold=threshold,
        )

    async def provider_failure(self, provider_name: str, consecutive_failures: int) -> None:
        await self.alert(
            title="Provider Consecutive Failures",
            message=f"Provider {provider_name!r} failed {consecutive_failures} times in a row",
            severity=AlertSeverity.CRITICAL if consecutive_failures >= 3 else AlertSeverity.WARNING,
            provider=provider_name, failures=consecutive_failures,
        )

    async def budget_exceeded(self, spent_usd: float, budget_usd: float) -> None:
        await self.alert(
            title="Budget Exceeded",
            message=f"Spent ${spent_usd:.4f} exceeds budget ${budget_usd:.4f}",
            severity=AlertSeverity.CRITICAL,
            spent_usd=spent_usd, budget_usd=budget_usd,
        )

    @property
    def history(self) -> list[Alert]:
        return list(self._history)


_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager


def reset_alert_manager() -> None:
    global _manager
    _manager = None
