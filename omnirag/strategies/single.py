"""Single execution strategy — run one pipeline."""

from __future__ import annotations

from typing import Any

from omnirag.core.models import GenerationResult
from omnirag.pipelines.schema import PipelineConfig
from omnirag.strategies.base import ExecutionStrategy


class SingleStrategy(ExecutionStrategy):
    """Execute only the first pipeline. Lowest latency."""

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
                metadata={"strategy": "single", "error": "no pipelines provided"},
            )
        return executor.execute(pipelines[0], query, **kwargs)
