"""Tests for observability — metrics and tracing."""

from omnirag.observability.metrics import MetricsCollector
from omnirag.observability.tracing import TracingManager


def test_counter():
    m = MetricsCollector()
    m.inc("requests_total", pipeline="test")
    m.inc("requests_total", pipeline="test")
    assert m.get_counter("requests_total", pipeline="test") == 2


def test_histogram():
    m = MetricsCollector()
    m.observe("latency", 0.5, pipeline="test")
    m.observe("latency", 1.2, pipeline="test")
    values = m.get_histogram("latency", pipeline="test")
    assert len(values) == 2
    assert sum(values) == 1.7


def test_gauge():
    m = MetricsCollector()
    m.set_gauge("active_tasks", 5)
    assert m.get_gauge("active_tasks") == 5
    m.set_gauge("active_tasks", 3)
    assert m.get_gauge("active_tasks") == 3


def test_timer():
    m = MetricsCollector()
    with m.timer("duration", op="test"):
        pass  # instant
    values = m.get_histogram("duration", op="test")
    assert len(values) == 1
    assert values[0] >= 0


def test_prometheus_export():
    m = MetricsCollector()
    m.inc("req_total", 5)
    m.observe("latency_seconds", 0.42)
    output = m.export_prometheus()
    assert "req_total" in output
    assert "latency_seconds" in output


def test_tracing_manager_noop():
    """TracingManager should work even without OTel SDK."""
    tm = TracingManager()
    with tm.span("test_span", {"key": "value"}):
        pass  # Should not raise
