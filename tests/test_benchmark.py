"""Tests for benchmark runner."""

from benchmarks.runner import geometric_mean, run_benchmark


def test_geometric_mean():
    assert round(geometric_mean([1.0, 1.0, 1.0]), 2) == 1.0
    assert round(geometric_mean([2.0, 8.0]), 2) == 4.0
    assert geometric_mean([]) == 0.0


def test_run_benchmark_completes():
    """Benchmark should run without errors (uses in-memory adapters)."""
    results = run_benchmark()
    assert "interpreted" in results
    assert "compiled" in results
    assert "speedup" in results
    assert results["interpreted"]["samples"] > 0
    assert results["compiled"]["samples"] > 0
