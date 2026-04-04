"""Prometheus metrics for OmniRAG.

Exposes pipeline latency, token usage, cache hits, adapter errors,
and confidence scores.
"""

from __future__ import annotations

import time
from typing import Any


class MetricsCollector:
    """Lightweight metrics collector (Prometheus-compatible export)."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Increment a counter."""
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record a histogram observation."""
        key = self._key(name, labels)
        self._histograms.setdefault(key, []).append(value)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge value."""
        key = self._key(name, labels)
        self._gauges[key] = value

    def timer(self, name: str, **labels: str) -> _Timer:
        """Context manager that records duration in a histogram."""
        return _Timer(self, name, labels)

    def get_counter(self, name: str, **labels: str) -> float:
        key = self._key(name, labels)
        return self._counters.get(key, 0)

    def get_histogram(self, name: str, **labels: str) -> list[float]:
        key = self._key(name, labels)
        return self._histograms.get(key, [])

    def get_gauge(self, name: str, **labels: str) -> float:
        key = self._key(name, labels)
        return self._gauges.get(key, 0)

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines: list[str] = []

        for key, value in sorted(self._counters.items()):
            name, label_str = self._parse_key(key)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{label_str} {value}")

        for key, values in sorted(self._histograms.items()):
            name, label_str = self._parse_key(key)
            count = len(values)
            total = sum(values)
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_count{label_str} {count}")
            lines.append(f"{name}_sum{label_str} {total:.4f}")

        for key, value in sorted(self._gauges.items()):
            name, label_str = self._parse_key(key)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{label_str} {value}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        label_parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_parts}}}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        if "{" in key:
            name, rest = key.split("{", 1)
            return name, "{" + rest
        return key, ""


class _Timer:
    """Context manager for timing operations."""

    def __init__(
        self, collector: MetricsCollector, name: str, labels: dict[str, str]
    ) -> None:
        self._collector = collector
        self._name = name
        self._labels = labels
        self._start = 0.0

    def __enter__(self) -> _Timer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.monotonic() - self._start
        self._collector.observe(self._name, duration, **self._labels)


# Global singleton
metrics = MetricsCollector()
