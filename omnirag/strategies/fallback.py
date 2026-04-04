"""Fallback execution strategy — try pipelines in sequence until one succeeds."""

from __future__ import annotations

from typing import Any

import structlog

from omnirag.core.exceptions import ExecutionError, StrategyExhaustedError
from omnirag.core.models import GenerationResult
from omnirag.pipelines.schema import PipelineConfig
from omnirag.strategies.base import ConditionFn, ExecutionStrategy, confidence_threshold

logger = structlog.get_logger()


class FallbackStrategy(ExecutionStrategy):
    """Try pipeline A; if condition fails, try B, then C, etc.

    Use for cost-sensitive or high-availability scenarios.
    """

    def __init__(self, condition: ConditionFn | None = None) -> None:
        self.condition = condition or confidence_threshold(0.7)

    def run(
        self,
        pipelines: list[PipelineConfig],
        query: str,
        executor: Any,
        **kwargs: Any,
    ) -> GenerationResult:
        if not pipelines:
            raise StrategyExhaustedError("No pipelines provided")

        last_result: GenerationResult | None = None

        for i, pipeline in enumerate(pipelines):
            try:
                result = executor.execute(pipeline, query, **kwargs)
                last_result = result

                if self.condition(result):
                    logger.info(
                        "strategy.fallback.accepted",
                        pipeline=pipeline.name,
                        index=i,
                        confidence=result.confidence,
                    )
                    result.metadata["strategy"] = "fallback"
                    result.metadata["pipeline_index"] = i
                    return result

                logger.info(
                    "strategy.fallback.rejected",
                    pipeline=pipeline.name,
                    index=i,
                    confidence=result.confidence,
                )
            except ExecutionError as e:
                logger.warning(
                    "strategy.fallback.error",
                    pipeline=pipeline.name,
                    index=i,
                    error=str(e),
                )
                continue

        if last_result is not None:
            last_result.metadata["strategy"] = "fallback"
            last_result.metadata["exhausted"] = True
            return last_result

        raise StrategyExhaustedError(
            f"All {len(pipelines)} pipelines failed or rejected"
        )
