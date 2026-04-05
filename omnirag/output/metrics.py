"""Prometheus metrics — 7 metric families for the output layer."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class MetricCounter:
    name: str
    labels: dict[str, int] = field(default_factory=dict)

    def inc(self, label: str = "default") -> None:
        self.labels[label] = self.labels.get(label, 0) + 1

    def get(self, label: str = "default") -> int:
        return self.labels.get(label, 0)


@dataclass
class MetricHistogram:
    name: str
    buckets: list[float] = field(default_factory=lambda: [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10])
    values: list[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self.values.append(value)

    def count(self) -> int:
        return len(self.values)

    def avg(self) -> float:
        return sum(self.values) / len(self.values) if self.values else 0

    def p95(self) -> float:
        if not self.values:
            return 0
        s = sorted(self.values)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]


@dataclass
class MetricGauge:
    name: str
    value: float = 0

    def set(self, v: float) -> None:
        self.value = v

    def inc(self) -> None:
        self.value += 1

    def dec(self) -> None:
        self.value = max(0, self.value - 1)


class OutputMetrics:
    """7 Prometheus metric families for the RAG output layer."""

    def __init__(self) -> None:
        self.chunks_indexed = MetricCounter("rag_chunks_indexed_total")
        self.query_latency = MetricHistogram("rag_query_latency_seconds")
        self.retrieval_fallback = MetricCounter("rag_retrieval_fallback_total")
        self.rate_limit_hits = MetricCounter("rag_rate_limit_hits_total")
        self.consistency_wait = MetricHistogram("rag_consistency_wait_seconds")
        self.websocket_connections = MetricGauge("rag_websocket_connections")
        self.webhook_delivery = MetricHistogram("rag_webhook_delivery_seconds")

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []

        lines.append(f"# HELP {self.chunks_indexed.name} Chunks written per store")
        lines.append(f"# TYPE {self.chunks_indexed.name} counter")
        for label, count in self.chunks_indexed.labels.items():
            lines.append(f'{self.chunks_indexed.name}{{store="{label}"}} {count}')

        lines.append(f"# HELP {self.query_latency.name} End-to-end query latency")
        lines.append(f"# TYPE {self.query_latency.name} histogram")
        lines.append(f"{self.query_latency.name}_count {self.query_latency.count()}")
        if self.query_latency.values:
            lines.append(f"{self.query_latency.name}_avg {self.query_latency.avg():.4f}")
            lines.append(f"{self.query_latency.name}_p95 {self.query_latency.p95():.4f}")

        lines.append(f"# HELP {self.retrieval_fallback.name} Fallback activations")
        lines.append(f"# TYPE {self.retrieval_fallback.name} counter")
        for label, count in self.retrieval_fallback.labels.items():
            lines.append(f'{self.retrieval_fallback.name}{{from="{label}"}} {count}')

        lines.append(f"# HELP {self.rate_limit_hits.name} Rate limit rejections")
        lines.append(f"# TYPE {self.rate_limit_hits.name} counter")
        for label, count in self.rate_limit_hits.labels.items():
            lines.append(f'{self.rate_limit_hits.name}{{endpoint="{label}"}} {count}')

        lines.append(f"# HELP {self.consistency_wait.name} Consistency polling time")
        lines.append(f"# TYPE {self.consistency_wait.name} histogram")
        lines.append(f"{self.consistency_wait.name}_count {self.consistency_wait.count()}")

        lines.append(f"# HELP {self.websocket_connections.name} Active WebSocket streams")
        lines.append(f"# TYPE {self.websocket_connections.name} gauge")
        lines.append(f"{self.websocket_connections.name} {self.websocket_connections.value}")

        lines.append(f"# HELP {self.webhook_delivery.name} Webhook delivery time")
        lines.append(f"# TYPE {self.webhook_delivery.name} histogram")
        lines.append(f"{self.webhook_delivery.name}_count {self.webhook_delivery.count()}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        return {
            "chunks_indexed": dict(self.chunks_indexed.labels),
            "query_latency": {"count": self.query_latency.count(), "avg_ms": round(self.query_latency.avg() * 1000, 1), "p95_ms": round(self.query_latency.p95() * 1000, 1)},
            "retrieval_fallbacks": dict(self.retrieval_fallback.labels),
            "rate_limit_hits": dict(self.rate_limit_hits.labels),
            "consistency_wait": {"count": self.consistency_wait.count()},
            "websocket_connections": self.websocket_connections.value,
            "webhook_deliveries": self.webhook_delivery.count(),
        }


_metrics = OutputMetrics()


def get_output_metrics() -> OutputMetrics:
    return _metrics
