"""Selective Execution Planner — compiles deterministic sub-graphs.

Algorithm:
1. Parse YAML into DAG
2. For each node, compute is_deterministic:
   - True if adapter is pure (chunking, embedding, vector search, reranking)
   - False if it involves LLM generation, agent decisions, or random sampling
3. Find maximal connected sub-graphs where all nodes are deterministic
4. Generate compiled Python functions for each sub-graph
5. Cache compiled functions by pipeline hash
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog

from omnirag.adapters.registry import AdapterRegistry, adapter_registry
from omnirag.core.maturity import MaturityLevel, get_maturity
from omnirag.pipelines.dag import PipelineDAG
from omnirag.pipelines.schema import PipelineConfig, StageConfig

logger = structlog.get_logger()

# Adapter categories that are deterministic (no LLM, no randomness)
_DETERMINISTIC_CATEGORIES = {"chunking", "embedding", "retrieval", "reranking", "ingestion"}

# Adapter categories that are non-deterministic
_NON_DETERMINISTIC_CATEGORIES = {"generation"}


class CompiledSubgraph:
    """A compiled deterministic sub-graph — executable as a single function."""

    def __init__(
        self,
        subgraph_id: str,
        stage_ids: list[str],
        stages: list[StageConfig],
        pipeline_hash: str,
    ) -> None:
        self.subgraph_id = subgraph_id
        self.stage_ids = stage_ids
        self.stages = stages
        self.pipeline_hash = pipeline_hash
        self.compiled_at = time.time()

    def execute(
        self,
        input_data: Any,
        query: str,
        registry: AdapterRegistry,
        **kwargs: Any,
    ) -> Any:
        """Execute the compiled sub-graph as a fused function.

        Instead of going through the executor stage-by-stage with full
        DAG overhead, this runs the deterministic stages in a tight loop
        with direct adapter calls and no intermediate logging/tracing.
        """
        current = input_data

        for stage in self.stages:
            if stage.adapter and registry.has(stage.adapter):
                adapter = registry.get(stage.adapter)
                category = getattr(adapter, "category", "")
                params = {**stage.params, **kwargs}

                if category == "ingestion":
                    current = adapter.ingest(current or params.get("source"), **params)
                elif category == "chunking":
                    current = adapter.chunk(current, **params)
                elif category == "embedding":
                    current = adapter.embed(current, **params)
                elif category == "retrieval":
                    if params.get("mode") == "upsert":
                        adapter.store(current, **params)
                    else:
                        current = adapter.retrieve(query, **params)
                elif category == "reranking":
                    current = adapter.rerank(current, **params)

        return current


class SelectiveExecutionPlanner:
    """Compiles deterministic pipeline sub-graphs into fused functions.

    The planner analyzes a pipeline DAG, identifies sub-graphs where
    all stages are deterministic (no LLM calls, no random sampling),
    and creates CompiledSubgraph objects that execute those stages
    as a single optimized function call.
    """

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry or adapter_registry
        self._cache: dict[str, list[CompiledSubgraph]] = {}

    def analyze(self, config: PipelineConfig) -> dict[str, bool]:
        """Analyze which stages are deterministic.

        A stage is deterministic if:
        - Its adapter exists in the registry
        - Its adapter category is in _DETERMINISTIC_CATEGORIES
        - Its adapter maturity is 'core' (full optimization support)

        Returns:
            Dict mapping stage_id -> is_deterministic
        """
        result: dict[str, bool] = {}

        for stage in config.stages:
            result[stage.id] = self._is_deterministic(stage)

        logger.info(
            "planner.analyze",
            pipeline=config.name,
            total_stages=len(config.stages),
            deterministic=sum(1 for v in result.values() if v),
            non_deterministic=sum(1 for v in result.values() if not v),
        )

        return result

    def _is_deterministic(self, stage: StageConfig) -> bool:
        """Check if a single stage is deterministic."""
        if not stage.adapter:
            return False

        if not self._registry.has(stage.adapter):
            return False

        adapter = self._registry.get(stage.adapter)
        category = getattr(adapter, "category", "")

        # Must be a deterministic category
        if category not in _DETERMINISTIC_CATEGORIES:
            return False

        # Must be core maturity for full optimization
        maturity = get_maturity(adapter)
        if maturity != MaturityLevel.CORE:
            return False

        return True

    def find_subgraphs(self, config: PipelineConfig) -> list[list[str]]:
        """Find maximal connected deterministic sub-graphs.

        Returns a list of sub-graphs, each being a list of stage IDs
        in topological order.
        """
        determinism = self.analyze(config)
        dag = PipelineDAG(config)
        order = dag.topological_sort()

        subgraphs: list[list[str]] = []
        current_subgraph: list[str] = []

        for stage_id in order:
            if determinism.get(stage_id, False):
                current_subgraph.append(stage_id)
            else:
                if len(current_subgraph) >= 2:
                    subgraphs.append(current_subgraph)
                current_subgraph = []

        # Don't forget the last subgraph
        if len(current_subgraph) >= 2:
            subgraphs.append(current_subgraph)

        logger.info(
            "planner.subgraphs",
            pipeline=config.name,
            subgraph_count=len(subgraphs),
            subgraph_sizes=[len(sg) for sg in subgraphs],
        )

        return subgraphs

    def compile(self, config: PipelineConfig) -> list[CompiledSubgraph]:
        """Compile all deterministic sub-graphs in a pipeline.

        Returns compiled sub-graph objects that can be executed directly.
        Results are cached by pipeline hash.
        """
        pipeline_hash = self._hash_pipeline(config)

        # Check cache
        if pipeline_hash in self._cache:
            logger.info("planner.cache_hit", pipeline=config.name)
            return self._cache[pipeline_hash]

        subgraph_ids = self.find_subgraphs(config)
        compiled: list[CompiledSubgraph] = []

        for i, stage_ids in enumerate(subgraph_ids):
            stages = [s for s in config.stages if s.id in stage_ids]
            # Preserve topological order
            stages.sort(key=lambda s: stage_ids.index(s.id))

            sg = CompiledSubgraph(
                subgraph_id=f"{config.name}_sg{i}",
                stage_ids=stage_ids,
                stages=stages,
                pipeline_hash=pipeline_hash,
            )
            compiled.append(sg)

            logger.info(
                "planner.compiled",
                subgraph=sg.subgraph_id,
                stages=stage_ids,
            )

        # Cache
        self._cache[pipeline_hash] = compiled
        return compiled

    def get_execution_plan(
        self, config: PipelineConfig
    ) -> list[dict[str, Any]]:
        """Get the full execution plan showing which stages are compiled vs interpreted.

        Returns a list of execution steps, each with:
        - type: "compiled" or "interpreted"
        - stages: list of stage IDs
        - subgraph_id: (only for compiled) the CompiledSubgraph ID
        """
        compiled = self.compile(config)
        compiled_ids: set[str] = set()
        for sg in compiled:
            compiled_ids.update(sg.stage_ids)

        dag = PipelineDAG(config)
        order = dag.topological_sort()

        plan: list[dict[str, Any]] = []
        i = 0

        while i < len(order):
            stage_id = order[i]

            # Check if this stage starts a compiled subgraph
            matching_sg = None
            for sg in compiled:
                if sg.stage_ids and sg.stage_ids[0] == stage_id:
                    matching_sg = sg
                    break

            if matching_sg:
                plan.append({
                    "type": "compiled",
                    "stages": matching_sg.stage_ids,
                    "subgraph_id": matching_sg.subgraph_id,
                })
                i += len(matching_sg.stage_ids)
            else:
                plan.append({
                    "type": "interpreted",
                    "stages": [stage_id],
                })
                i += 1

        return plan

    def invalidate(self, pipeline_name: str | None = None) -> None:
        """Invalidate cached compilations.

        Args:
            pipeline_name: If given, only invalidate that pipeline. Otherwise clear all.
        """
        if pipeline_name is None:
            self._cache.clear()
        else:
            keys_to_remove = [
                k for k in self._cache
                if k.startswith(pipeline_name)
            ]
            for k in keys_to_remove:
                del self._cache[k]

    @staticmethod
    def _hash_pipeline(config: PipelineConfig) -> str:
        """Generate a stable hash for a pipeline configuration."""
        data = config.model_dump_json(exclude_none=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
