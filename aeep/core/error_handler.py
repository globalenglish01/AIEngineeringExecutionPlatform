"""Global error handler — classifies, logs, and triggers recovery actions."""

from __future__ import annotations

import traceback
from typing import Any

from aeep.core.exceptions import (
    ConfigError,
    PlatformError,
    ProviderRateLimitError,
    QualityGateFailedError,
)
from aeep.observability.logging import get_logger

log = get_logger()


class TransientError(PlatformError):
    """Network timeouts, rate-limits — retryable."""


class PermanentError(PlatformError):
    """Config errors, permission errors — not retryable."""


class QualityError(PlatformError):
    """Output quality below threshold — triggers repair loop."""

    def __init__(self, message: str, score: float, threshold: float) -> None:
        super().__init__(message)
        self.score = score
        self.threshold = threshold


class BudgetError(PlatformError):
    """Spending limit exceeded — pause and alert."""

    def __init__(self, spent: float, budget: float) -> None:
        super().__init__(f"Budget exceeded: ${spent:.4f} > ${budget:.4f}")
        self.spent = spent
        self.budget = budget


def classify(exc: Exception) -> str:
    """Return 'transient' | 'permanent' | 'quality' | 'budget' | 'unknown'."""
    if isinstance(exc, (TransientError, ProviderRateLimitError, ConnectionError, TimeoutError)):
        return "transient"
    if isinstance(exc, (PermanentError, ConfigError, PermissionError, ValueError)):
        return "permanent"
    if isinstance(exc, (QualityError, QualityGateFailedError)):
        return "quality"
    if isinstance(exc, BudgetError):
        return "budget"
    return "unknown"


async def handle_error(
    exc: Exception,
    context: dict[str, Any] | None = None,
    send_alert: bool = True,
) -> None:
    """Log the error, optionally send an alert."""
    error_class = classify(exc)
    tb = traceback.format_exc()

    log.error(
        "unhandled_error",
        error_class=error_class,
        error_type=type(exc).__name__,
        message=str(exc),
        traceback=tb,
        context=context or {},
    )

    if send_alert:
        try:
            from aeep.observability.alerting import AlertSeverity, get_alert_manager
            mgr = get_alert_manager()
            severity = AlertSeverity.CRITICAL if error_class == "permanent" else AlertSeverity.WARNING
            await mgr.alert(
                title=f"{error_class.title()} Error: {type(exc).__name__}",
                message=str(exc),
                severity=severity,
                error_class=error_class,
            )
        except Exception:
            pass
