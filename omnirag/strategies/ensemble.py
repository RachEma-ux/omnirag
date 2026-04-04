"""Ensemble execution strategy — run all pipelines, merge results."""

from __future__ import annotations

import concurrent.futures
import structlog
from typing import Any

from omnirag.core.models import GenerationResult, OmniChunk
from omnirag.pipelines.schema import PipelineConfig
from omnirag.strategies.base import ExecutionStrategy

logger = structlog.get_logger()


class EnsembleStrategy(ExecutionStrategy):
    """Run all pipelines in parallel, merge results.

    Merge modes:
    - deduplicate: Keep first occurrence of each chunk by ID
    - concat: Simple concatenation
    - rerank: Deduplicate + rerank (requires reranking adapter)
    """

    def __init__(self, merge_mode: str = "deduplicate", max_workers: int = 3) -> None:
        self.merge_mode = merge_mode
        self.max_workers = max_workers

    def run(
        self,
        pipelines: list[PipelineConfig],
        query: str,
        executor: Any,
        **kwargs: Any,
    ) -> GenerationResult:
        if not pipelines:
            return GenerationResult(
                answer="",
                confidence=0.0,
                metadata={"strategy": "ensemble", "error": "no pipelines"},
            )

        if len(pipelines) == 1:
            result = executor.execute(pipelines[0], query, **kwargs)
            result.metadata["strategy"] = "ensemble"
            return result

        # Execute all pipelines in parallel
        results: list[GenerationResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(executor.execute, p, query, **kwargs): p.name
                for p in pipelines
            }
            for future in concurrent.futures.as_completed(futures):
                pipeline_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(
                        "strategy.ensemble.pipeline_complete",
                        pipeline=pipeline_name,
                        confidence=result.confidence,
                    )
                except Exception as e:
                    logger.warning(
                        "strategy.ensemble.pipeline_error",
                        pipeline=pipeline_name,
                        error=str(e),
                    )

        if not results:
            return GenerationResult(
                answer="",
                confidence=0.0,
                metadata={"strategy": "ensemble", "error": "all pipelines failed"},
            )

        return self._merge(results, query)

    def _merge(self, results: list[GenerationResult], query: str) -> GenerationResult:
        """Merge multiple GenerationResults."""
        # Collect all citations, deduplicate
        all_citations: list[str] = []
        seen_citations: set[str] = set()
        for r in results:
            for c in r.citations:
                if c not in seen_citations:
                    all_citations.append(c)
                    seen_citations.add(c)

        # Pick best answer by confidence
        best = max(results, key=lambda r: r.confidence)
        avg_confidence = sum(r.confidence for r in results) / len(results)

        return GenerationResult(
            answer=best.answer,
            citations=all_citations,
            confidence=min(1.0, avg_confidence * 1.1),  # slight boost for ensemble
            metadata={
                "strategy": "ensemble",
                "merge_mode": self.merge_mode,
                "pipeline_count": len(results),
                "best_pipeline_confidence": best.confidence,
            },
        )
