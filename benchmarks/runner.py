"""OmniRAG benchmark runner.

Compares interpreted vs compiled execution across multiple pipeline
configurations and query sets. Reports geometric mean speedup.

Usage:
    python -m benchmarks.runner
"""

from __future__ import annotations

import math
import time
from typing import Any

from omnirag.adapters.chunking import RecursiveChunkerAdapter
from omnirag.adapters.ingestion import FileLoaderAdapter
from omnirag.adapters.memory import MemoryVectorAdapter
from omnirag.adapters.registry import AdapterRegistry
from omnirag.core.models import OmniChunk, OmniDocument
from omnirag.pipelines.executor import InterpretedExecutor
from omnirag.pipelines.schema import ExecutionConfig, PipelineConfig, StageConfig


def _create_test_registry() -> AdapterRegistry:
    """Create a registry with test adapters."""
    reg = AdapterRegistry()
    reg.register("file_loader", FileLoaderAdapter)
    reg.register("recursive_splitter", RecursiveChunkerAdapter)
    reg.register("memory", MemoryVectorAdapter)
    return reg


def _deterministic_pipeline() -> PipelineConfig:
    """Pipeline with only deterministic stages (no LLM)."""
    return PipelineConfig(
        name="bench_deterministic",
        execution=ExecutionConfig(strategy="single"),
        stages=[
            StageConfig(id="load", adapter="file_loader", params={"source": "."}),
            StageConfig(id="chunk", adapter="recursive_splitter", input="load"),
            StageConfig(
                id="store",
                adapter="memory",
                input="chunk",
                params={"mode": "upsert"},
            ),
            StageConfig(id="retrieve", adapter="memory", input="query"),
        ],
    )


def _benchmark_executor(
    executor: InterpretedExecutor,
    config: PipelineConfig,
    queries: list[str],
    runs: int = 5,
) -> list[float]:
    """Run queries and return per-query latencies in ms."""
    latencies: list[float] = []

    # Warmup
    for q in queries[:1]:
        try:
            executor.execute(config, q)
        except Exception:
            pass

    for _ in range(runs):
        for q in queries:
            start = time.monotonic()
            try:
                executor.execute(config, q)
            except Exception:
                pass
            elapsed = (time.monotonic() - start) * 1000
            latencies.append(elapsed)

    return latencies


def geometric_mean(values: list[float]) -> float:
    """Compute geometric mean of positive values."""
    if not values:
        return 0.0
    log_sum = sum(math.log(max(v, 0.001)) for v in values)
    return math.exp(log_sum / len(values))


def run_benchmark() -> dict[str, Any]:
    """Run full benchmark comparing interpreted vs compiled."""
    reg = _create_test_registry()
    config = _deterministic_pipeline()
    queries = [
        "What is RAG?",
        "Explain embeddings",
        "How does vector search work?",
        "What is chunking?",
        "Define retrieval augmented generation",
    ]

    # Interpreted mode
    interpreted = InterpretedExecutor(registry=reg, use_compiler=False)
    interp_latencies = _benchmark_executor(interpreted, config, queries)

    # Compiled mode
    compiled = InterpretedExecutor(registry=reg, use_compiler=True)
    compiled_latencies = _benchmark_executor(compiled, config, queries)

    interp_mean = geometric_mean(interp_latencies)
    compiled_mean = geometric_mean(compiled_latencies)
    speedup = interp_mean / compiled_mean if compiled_mean > 0 else 0

    results = {
        "interpreted": {
            "geometric_mean_ms": round(interp_mean, 3),
            "min_ms": round(min(interp_latencies), 3),
            "max_ms": round(max(interp_latencies), 3),
            "samples": len(interp_latencies),
        },
        "compiled": {
            "geometric_mean_ms": round(compiled_mean, 3),
            "min_ms": round(min(compiled_latencies), 3),
            "max_ms": round(max(compiled_latencies), 3),
            "samples": len(compiled_latencies),
        },
        "speedup": round(speedup, 2),
        "queries": len(queries),
        "runs_per_query": 5,
    }

    return results


def print_report(results: dict[str, Any]) -> None:
    """Print benchmark results as a formatted table."""
    print("\n" + "=" * 60)
    print("  OmniRAG Benchmark: Interpreted vs Compiled")
    print("=" * 60)
    print(f"  Queries: {results['queries']}")
    print(f"  Runs per query: {results['runs_per_query']}")
    print("-" * 60)

    for mode in ("interpreted", "compiled"):
        d = results[mode]
        print(f"  {mode.upper()}")
        print(f"    Geometric mean: {d['geometric_mean_ms']:.3f} ms")
        print(f"    Min: {d['min_ms']:.3f} ms")
        print(f"    Max: {d['max_ms']:.3f} ms")
        print(f"    Samples: {d['samples']}")
        print()

    print(f"  SPEEDUP: {results['speedup']:.2f}x")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    results = run_benchmark()
    print_report(results)
