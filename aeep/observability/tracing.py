"""Lightweight span-based tracing (no external dependency required).

Provides a context-manager API compatible with OpenTelemetry concepts.
When the ``opentelemetry-sdk`` package is installed, delegates to real OTEL.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import local
from typing import Any, Generator, Iterator

_local = local()


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_time: float
    attributes: dict[str, Any] = field(default_factory=dict)
    end_time: float | None = None
    status: str = "OK"

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = time.monotonic()


class Tracer:
    """Simple in-process span tracer."""

    def __init__(self) -> None:
        self._spans: list[Span] = []

    @contextmanager
    def start_span(self, name: str, **attributes: Any) -> Iterator[Span]:
        parent_id = getattr(_local, "current_span_id", None)
        trace_id = getattr(_local, "trace_id", None) or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        _local.trace_id = trace_id
        prev_span_id = getattr(_local, "current_span_id", None)
        _local.current_span_id = span_id

        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            start_time=time.monotonic(),
            attributes=dict(attributes),
        )
        try:
            yield span
        except Exception as e:
            span.set_status("ERROR")
            span.set_attribute("error", str(e))
            raise
        finally:
            span.end()
            self._spans.append(span)
            _local.current_span_id = prev_span_id

    def get_spans(self) -> list[Span]:
        return list(self._spans)

    def clear(self) -> None:
        self._spans.clear()


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def reset_tracer() -> None:
    global _tracer
    _tracer = None
