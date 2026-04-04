"""Base execution strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from omnirag.core.models import GenerationResult
from omnirag.pipelines.schema import PipelineConfig


# Condition function type: takes GenerationResult, returns True if result is acceptable
ConditionFn = Callable[[GenerationResult], bool]


def confidence_threshold(min_conf: float = 0.7) -> ConditionFn:
    """Built-in condition: result confidence must meet threshold."""
    def check(result: GenerationResult) -> bool:
        return result.confidence >= min_conf
    return check


def empty_result() -> ConditionFn:
    """Built-in condition: result must have a non-empty answer."""
    def check(result: GenerationResult) -> bool:
        return bool(result.answer and result.answer.strip())
    return check


class ExecutionStrategy(ABC):
    """Abstract base class for execution strategies."""

    @abstractmethod
    def run(
        self,
        pipelines: list[PipelineConfig],
        query: str,
        executor: Any,
        **kwargs: Any,
    ) -> GenerationResult:
        """Execute one or more pipelines according to the strategy.

        Args:
            pipelines: List of pipeline configs to execute.
            query: User query.
            executor: InterpretedExecutor instance.
            **kwargs: Additional parameters.

        Returns:
            Final GenerationResult.
        """
