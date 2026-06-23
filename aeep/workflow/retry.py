"""Retry utilities with exponential back-off."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

from aeep.core.exceptions import (
    ConfigError,
    ProviderRateLimitError,
    QualityGateFailedError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Errors that should NOT be retried (permanent failures)
_NON_RETRYABLE = (
    ConfigError,
    ValueError,
    TypeError,
    PermissionError,
)


def is_retryable(exc: BaseException) -> bool:
    """Return True if retrying the operation makes sense."""
    if isinstance(exc, _NON_RETRYABLE):
        return False
    if isinstance(exc, QualityGateFailedError):
        return False  # quality gate fail → fix content, not retry blindly
    return True


async def retry_async(
    fn: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retryable_check: Callable[[BaseException], bool] = is_retryable,
    **kwargs: Any,
) -> Any:
    """Call *fn* with exponential back-off on transient failures.

    Args:
        fn              async callable to retry
        max_attempts    total number of attempts (including the first)
        initial_delay   seconds to wait before the second attempt
        backoff_factor  multiplier applied after each failure
        max_delay       upper cap on wait time between attempts
        retryable_check predicate: return True if the exception warrants a retry
    """
    delay = initial_delay
    last_exc: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except ProviderRateLimitError as exc:
            last_exc = exc
            wait = exc.retry_after or delay
            logger.warning(
                "Attempt %d/%d — rate limited, waiting %ds: %s",
                attempt, max_attempts, wait, exc,
            )
        except BaseException as exc:
            last_exc = exc
            if not retryable_check(exc):
                logger.error("Non-retryable error on attempt %d: %s", attempt, exc)
                raise
            wait = delay
            logger.warning(
                "Attempt %d/%d failed (%s), retrying in %.1fs",
                attempt, max_attempts, type(exc).__name__, wait,
            )

        if attempt < max_attempts:
            await asyncio.sleep(min(wait, max_delay))
            delay = min(delay * backoff_factor, max_delay)

    assert last_exc is not None
    raise last_exc
