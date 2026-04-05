"""Answer tracing — full query audit trail (QueryPlan → Context → LLM → Answer)."""

from __future__ import annotations

import time

import structlog

from omnirag.models.canonical import AnswerTrace, MetricEvent
from omnirag.intake.storage.repository import get_repository

logger = structlog.get_logger(__name__)


class TraceRecorder:
    """Records and retrieves query traces for audit + observability."""

    def __init__(self) -> None:
        self._traces: dict[str, AnswerTrace] = {}
        self._metrics: list[MetricEvent] = []

    async def record_trace(self, trace: AnswerTrace) -> None:
        """Persist a query trace."""
        self._traces[trace.id] = trace
        repo = get_repository()
        await repo.upsert("query_traces", "id", {
            "id": trace.id,
            "answer_id": trace.answer_id,
            "selected_mode": trace.mode,
            "llm_model": trace.llm_model,
            "token_input": trace.token_usage.get("input", 0),
            "token_output": trace.token_usage.get("output", 0),
            "latency_ms": int(trace.latency_ms),
            "cache_hit": trace.cache_hit,
            "acl_filtered_nodes": trace.acl_filtered_nodes,
            "query_plan": trace.query_plan,
            "created_at": trace.created_at,
        })
        logger.info("trace.recorded", trace_id=trace.id, mode=trace.mode, latency=trace.latency_ms)

    async def record_metric(self, event: MetricEvent) -> None:
        """Persist a metric event."""
        self._metrics.append(event)
        repo = get_repository()
        await repo.upsert("metric_events", "id", event.to_dict())

    def get_trace(self, trace_id: str) -> AnswerTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self, limit: int = 50, mode: str | None = None) -> list[dict]:
        traces = list(self._traces.values())
        if mode:
            traces = [t for t in traces if t.mode == mode]
        traces.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in traces[:limit]]

    def get_metrics(self, name: str | None = None, limit: int = 100) -> list[dict]:
        filtered = self._metrics
        if name:
            filtered = [m for m in filtered if m.name == name]
        return [m.to_dict() for m in sorted(filtered, key=lambda m: m.timestamp, reverse=True)[:limit]]

    def stats(self) -> dict:
        return {"traces": len(self._traces), "metrics": len(self._metrics)}


_recorder = TraceRecorder()


def get_trace_recorder() -> TraceRecorder:
    return _recorder
