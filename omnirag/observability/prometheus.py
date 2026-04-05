"""Production Prometheus exporter — 8 mandatory metric families + output layer metrics.

Exposed at /metrics in Prometheus text format.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class PrometheusExporter:
    """Collects and exports all platform metrics in Prometheus text format."""

    def __init__(self) -> None:
        self._counters: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}

    def counter_inc(self, name: str, labels: str = "", value: float = 1) -> None:
        self._counters[name][labels] += value

    def histogram_observe(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def gauge_set(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def export(self) -> str:
        """Export all metrics in Prometheus text exposition format."""
        lines: list[str] = []

        # Counters
        for name, label_values in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            for labels, value in label_values.items():
                label_str = f"{{{labels}}}" if labels else ""
                lines.append(f"{name}{label_str} {value}")

        # Histograms (simplified: count + sum + quantiles)
        for name, values in self._histograms.items():
            if not values:
                continue
            lines.append(f"# TYPE {name} histogram")
            sorted_v = sorted(values)
            count = len(sorted_v)
            total = sum(sorted_v)
            lines.append(f"{name}_count {count}")
            lines.append(f"{name}_sum {total:.4f}")
            # Quantiles
            for q in (0.5, 0.95, 0.99):
                idx = int(count * q)
                lines.append(f'{name}{{quantile="{q}"}} {sorted_v[min(idx, count-1)]:.4f}')

        # Gauges
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        return {
            "counters": dict(self._counters),
            "histograms": {k: {"count": len(v), "avg": sum(v)/len(v) if v else 0} for k, v in self._histograms.items()},
            "gauges": dict(self._gauges),
        }


# Singleton
_exporter = PrometheusExporter()


def get_prometheus() -> PrometheusExporter:
    return _exporter


# ─── Convenience functions for the 8 mandatory metric families ───

def record_query_latency(mode: str, latency_s: float, fallback: bool = False) -> None:
    labels = f'mode="{mode}",fallback="{str(fallback).lower()}"'
    _exporter.histogram_observe("graphrag_latency_ms", latency_s * 1000)
    _exporter.counter_inc("graphrag_queries_total", f'mode="{mode}"')

def record_quality(mode: str, confidence: float, coverage: float) -> None:
    _exporter.gauge_set(f"graphrag_quality_confidence_{mode}", confidence)
    _exporter.gauge_set(f"graphrag_quality_coverage_{mode}", coverage)

def record_routing(from_mode: str, to_mode: str) -> None:
    _exporter.counter_inc("graphrag_routing_fallback_total", f'from="{from_mode}",to="{to_mode}"')

def record_cache_hit(mode: str) -> None:
    _exporter.counter_inc("graphrag_cache_hit_total", f'mode="{mode}"')

def record_tokens(operation: str, count: int) -> None:
    _exporter.counter_inc("graphrag_tokens_used_total", f'operation="{operation}"', count)

def record_staleness(count: int) -> None:
    _exporter.gauge_set("graphrag_stale_communities_count", count)

def record_community_update(duration_s: float, update_type: str = "incremental") -> None:
    _exporter.histogram_observe("graphrag_community_update_seconds", duration_s)

def record_acl_denial(mode: str) -> None:
    _exporter.counter_inc("graphrag_acl_denials_total", f'mode="{mode}"')
