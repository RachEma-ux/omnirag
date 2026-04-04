"""Selective Execution Planner — compiles deterministic sub-graphs.

Phase 2 implementation. This module will:
1. Parse YAML into DAG
2. Detect deterministic sub-graphs (no LLM, no random, no I/O side effects)
3. Generate pure Python functions via AST
4. Cache compiled functions by pipeline hash

Currently a placeholder.
"""

from __future__ import annotations

from omnirag.pipelines.schema import PipelineConfig


class SelectiveExecutionPlanner:
    """Compiles deterministic pipeline sub-graphs into pure Python functions."""

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def analyze(self, config: PipelineConfig) -> dict[str, bool]:
        """Analyze which stages are deterministic.

        Returns:
            Dict mapping stage_id -> is_deterministic
        """
        # TODO: Implement determinism predicate
        return {stage.id: False for stage in config.stages}

    def compile(self, config: PipelineConfig) -> None:
        """Compile deterministic sub-graphs to Python functions.

        Not yet implemented — all stages run in interpreted mode.
        """
        raise NotImplementedError("Compiler not yet implemented (Phase 2)")
