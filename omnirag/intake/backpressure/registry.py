"""Backpressure registry — collects health signals from index writers."""

from __future__ import annotations

import time

from omnirag.intake.models import IndexerHealth, IndexerStatus


# Thresholds from reference spec
BACKLOG_QUEUE_DEPTH = 10_000
BACKLOG_LATENCY_MS = 5_000
CRITICAL_ERROR_RATE = 0.1
CRITICAL_LATENCY_MS = 30_000


class BackpressureRegistry:
    """Central component collecting health metrics from all index writers."""

    def __init__(self) -> None:
        self._health: dict[str, IndexerHealth] = {}

    def report_health(self, indexer_id: str, health: IndexerHealth) -> None:
        """Update health for an indexer."""
        health.indexer_id = indexer_id
        health.recorded_at = time.time()

        # Auto-classify status
        if health.error_rate > CRITICAL_ERROR_RATE or health.avg_latency_ms > CRITICAL_LATENCY_MS:
            health.status = IndexerStatus.CRITICAL
        elif health.queue_depth > BACKLOG_QUEUE_DEPTH or health.avg_latency_ms > BACKLOG_LATENCY_MS:
            health.status = IndexerStatus.BACKLOGGED
        else:
            health.status = IndexerStatus.HEALTHY

        self._health[indexer_id] = health

    def get_health(self, indexer_id: str) -> IndexerHealth | None:
        return self._health.get(indexer_id)

    def is_healthy(self) -> bool:
        """All indexers healthy?"""
        if not self._health:
            return True
        return all(h.status == IndexerStatus.HEALTHY for h in self._health.values())

    def get_blocked_indexers(self) -> list[str]:
        """Return IDs of backlogged or critical indexers."""
        return [
            h.indexer_id for h in self._health.values()
            if h.status in (IndexerStatus.BACKLOGGED, IndexerStatus.CRITICAL)
        ]

    def get_all(self) -> dict[str, dict]:
        return {
            k: {
                "queue_depth": v.queue_depth,
                "avg_latency_ms": v.avg_latency_ms,
                "error_rate": v.error_rate,
                "status": v.status.value,
                "recorded_at": v.recorded_at,
            }
            for k, v in self._health.items()
        }


_registry = BackpressureRegistry()


def get_backpressure_registry() -> BackpressureRegistry:
    return _registry
