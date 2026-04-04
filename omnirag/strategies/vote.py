"""Vote execution strategy — majority vote across pipeline answers."""

from __future__ import annotations

import concurrent.futures
from typing import Any

import structlog

from omnirag.core.models import GenerationResult
from omnirag.pipelines.schema import PipelineConfig
from omnirag.strategies.base import ExecutionStrategy

logger = structlog.get_logger()


class VoteStrategy(ExecutionStrategy):
    """Run all pipelines, extract answers, and take majority vote.

    Best for QA tasks where disagreement resolution is needed.
    Votes are weighted by confidence scores.
    """

    def __init__(self, max_workers: int = 3) -> None:
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
                metadata={"strategy": "vote", "error": "no pipelines"},
            )

        # Execute all pipelines
        results: list[GenerationResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(executor.execute, p, query, **kwargs): p.name
                for p in pipelines
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.warning("strategy.vote.pipeline_error", error=str(e))

        if not results:
            return GenerationResult(
                answer="",
                confidence=0.0,
                metadata={"strategy": "vote", "error": "all pipelines failed"},
            )

        if len(results) == 1:
            results[0].metadata["strategy"] = "vote"
            return results[0]

        return self._tally_votes(results)

    def _tally_votes(self, results: list[GenerationResult]) -> GenerationResult:
        """Tally votes across results, weighted by confidence."""
        # Normalize answers for comparison (lowercase, strip)
        normalized: dict[str, list[GenerationResult]] = {}
        for r in results:
            key = r.answer.strip().lower()
            normalized.setdefault(key, []).append(r)

        # Find answer with highest total weighted confidence
        best_key = ""
        best_score = 0.0
        for key, group in normalized.items():
            score = sum(r.confidence for r in group)
            if score > best_score:
                best_score = score
                best_key = key

        winners = normalized[best_key]
        best_result = max(winners, key=lambda r: r.confidence)
        vote_share = len(winners) / len(results)

        return GenerationResult(
            answer=best_result.answer,
            citations=best_result.citations,
            confidence=min(1.0, best_result.confidence * (0.5 + 0.5 * vote_share)),
            metadata={
                "strategy": "vote",
                "total_votes": len(results),
                "winning_votes": len(winners),
                "vote_share": round(vote_share, 2),
                "unique_answers": len(normalized),
            },
        )
