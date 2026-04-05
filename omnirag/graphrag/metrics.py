"""GraphRAG Prometheus metrics — 8 metric families."""

from __future__ import annotations

from omnirag.output.metrics import MetricCounter, MetricHistogram, MetricGauge


class GraphRAGMetrics:
    def __init__(self) -> None:
        self.query_latency = MetricHistogram("graphrag_query_latency_seconds")
        self.retrieval_confidence = MetricGauge("graphrag_retrieval_confidence")
        self.retrieval_coverage = MetricGauge("graphrag_retrieval_coverage")
        self.router_fallback = MetricCounter("graphrag_router_fallback_total")
        self.cache_hit = MetricCounter("graphrag_cache_hit_total")
        self.community_update_duration = MetricHistogram("graphrag_community_update_duration_seconds")
        self.llm_tokens = MetricCounter("graphrag_llm_tokens_total")
        self.stale_communities = MetricGauge("graphrag_stale_communities_count")

    def to_dict(self) -> dict:
        return {
            "query_latency": {"count": self.query_latency.count(), "avg": self.query_latency.avg()},
            "confidence": self.retrieval_confidence.value,
            "coverage": self.retrieval_coverage.value,
            "router_fallbacks": dict(self.router_fallback.labels),
            "cache_hits": dict(self.cache_hit.labels),
            "stale_communities": self.stale_communities.value,
        }


_metrics = GraphRAGMetrics()


def get_graphrag_metrics() -> GraphRAGMetrics:
    return _metrics
