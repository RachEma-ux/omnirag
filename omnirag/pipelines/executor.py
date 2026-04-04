"""Interpreted pipeline executor.

Walks the DAG in topological order, executing each stage via its
adapter or runtime, passing canonical models between stages.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from omnirag.adapters.registry import AdapterRegistry, adapter_registry
from omnirag.core.exceptions import StageExecutionError
from omnirag.core.models import GenerationResult
from omnirag.pipelines.dag import PipelineDAG
from omnirag.pipelines.schema import PipelineConfig, StageConfig

logger = structlog.get_logger()


class InterpretedExecutor:
    """Execute a pipeline by interpreting the DAG stage by stage."""

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.registry = registry or adapter_registry

    def execute(
        self,
        config: PipelineConfig,
        query: str,
        **kwargs: Any,
    ) -> GenerationResult:
        """Execute a pipeline end-to-end.

        Args:
            config: Validated pipeline configuration.
            query: User query string.
            **kwargs: Additional parameters passed to stages.

        Returns:
            GenerationResult from the final stage.
        """
        dag = PipelineDAG(config)
        execution_order = dag.topological_sort()

        # Stage outputs indexed by stage ID
        outputs: dict[str, Any] = {"query": query}
        start_time = time.monotonic()

        logger.info(
            "pipeline.execute.start",
            pipeline=config.name,
            stages=len(execution_order),
            strategy=config.execution.strategy,
        )

        for stage_id in execution_order:
            stage = dag.get_stage(stage_id)
            stage_start = time.monotonic()

            try:
                result = self._execute_stage(stage, outputs, query, **kwargs)
                outputs[stage_id] = result

                logger.info(
                    "stage.execute.complete",
                    stage=stage_id,
                    duration_ms=round((time.monotonic() - stage_start) * 1000, 2),
                )
            except Exception as e:
                logger.error(
                    "stage.execute.error",
                    stage=stage_id,
                    error=str(e),
                )
                raise StageExecutionError(stage_id, str(e)) from e

        total_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info("pipeline.execute.complete", pipeline=config.name, duration_ms=total_ms)

        # Return the output of the last stage
        last_stage_id = execution_order[-1]
        final_output = outputs[last_stage_id]

        if isinstance(final_output, GenerationResult):
            return final_output

        # Wrap non-GenerationResult output
        return GenerationResult(
            answer=str(final_output),
            confidence=0.5,
            metadata={"pipeline": config.name, "duration_ms": total_ms},
        )

    def _execute_stage(
        self,
        stage: StageConfig,
        outputs: dict[str, Any],
        query: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a single stage."""
        # Resolve input data
        input_data = None
        if stage.input:
            input_data = outputs.get(stage.input)
            if input_data is None and stage.input != "query":
                raise StageExecutionError(
                    stage.id, f"Input '{stage.input}' not found in outputs"
                )

        # Execute via adapter (shared runtime)
        if stage.adapter and self.registry.has(stage.adapter):
            adapter = self.registry.get(stage.adapter)
            return self._call_adapter(adapter, stage, input_data, query, **kwargs)

        # Execute via runtime component
        if stage.runtime != "shared" and stage.component:
            return self._call_runtime(stage, input_data, query, **kwargs)

        raise StageExecutionError(
            stage.id,
            f"No adapter '{stage.adapter}' registered and no runtime component specified",
        )

    def _call_adapter(
        self,
        adapter: Any,
        stage: StageConfig,
        input_data: Any,
        query: str,
        **kwargs: Any,
    ) -> Any:
        """Call the appropriate adapter method based on stage category."""
        params = {**stage.params, **kwargs}
        category = getattr(adapter, "category", "")

        if category == "ingestion":
            return adapter.ingest(input_data or params.get("source"), **params)
        elif category == "chunking":
            return adapter.chunk(input_data, **params)
        elif category == "embedding":
            return adapter.embed(input_data, **params)
        elif category == "retrieval":
            if stage.params.get("mode") == "upsert":
                adapter.store(input_data, **params)
                return input_data
            return adapter.retrieve(query, **params)
        elif category == "reranking":
            return adapter.rerank(input_data, **params)
        elif category == "generation":
            context = input_data if isinstance(input_data, list) else []
            return adapter.generate(query, context, **params)
        else:
            raise StageExecutionError(
                stage.id, f"Unknown adapter category: {category}"
            )

    def _call_runtime(
        self,
        stage: StageConfig,
        input_data: Any,
        query: str,
        **kwargs: Any,
    ) -> Any:
        """Call a native runtime component."""
        # TODO: Load runtime, call component
        raise StageExecutionError(
            stage.id,
            f"Runtime '{stage.runtime}' component execution not yet implemented",
        )
