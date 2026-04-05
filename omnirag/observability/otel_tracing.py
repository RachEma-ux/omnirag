"""OpenTelemetry tracing — W3C traceparent, span types for each pipeline stage."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Span:
    """Lightweight span compatible with OpenTelemetry format."""
    trace_id: str = ""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    name: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float = 0

    def finish(self) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class Tracer:
    """Lightweight tracer (upgradeable to OpenTelemetry SDK).

    Span types:
    - extraction.entity, extraction.relationship
    - resolution.cluster, resolution.verify
    - graph.build, graph.community
    - retrieval.hybrid_search, retrieval.rerank
    - generation.llm_call
    - consistency.wait
    - router.classify
    """

    def __init__(self, sample_rate: float = 0.01) -> None:
        self.sample_rate = sample_rate
        self._spans: list[Span] = []
        self._active_traces: dict[str, list[Span]] = {}

    def start_trace(self) -> str:
        """Start a new trace. Returns trace_id."""
        import random
        if random.random() > self.sample_rate:
            return ""  # Not sampled
        trace_id = uuid.uuid4().hex[:32]
        self._active_traces[trace_id] = []
        return trace_id

    def start_span(self, trace_id: str, name: str, parent_span_id: str | None = None,
                   tags: dict | None = None) -> Span:
        """Start a span within a trace."""
        span = Span(trace_id=trace_id, name=name, parent_span_id=parent_span_id, tags=tags or {})
        if trace_id in self._active_traces:
            self._active_traces[trace_id].append(span)
        self._spans.append(span)
        return span

    def finish_span(self, span: Span) -> None:
        span.finish()

    def get_trace(self, trace_id: str) -> list[dict]:
        spans = self._active_traces.get(trace_id, [])
        return [{
            "span_id": s.span_id, "name": s.name, "tags": s.tags,
            "duration_ms": round(s.duration_ms, 1), "parent": s.parent_span_id,
        } for s in spans]

    def recent_spans(self, limit: int = 50) -> list[dict]:
        return [{
            "trace_id": s.trace_id, "span_id": s.span_id, "name": s.name,
            "duration_ms": round(s.duration_ms, 1), "tags": s.tags,
        } for s in sorted(self._spans[-limit:], key=lambda s: s.start_time, reverse=True)]


_tracer = Tracer()


def get_tracer() -> Tracer:
    return _tracer
