"""Pipeline executor — interpreted and compiled modes.

Walks the DAG in topological order, executing each stage via its
adapter or runtime, passing canonical models between stages.

When a SelectiveExecutionPlanner is provided, deterministic sub-graphs
are executed as fused compiled functions for better performance.
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
    """Execute a pipeline by interpreting the DAG stage by stage.

    Optionally uses the Selective Execution Planner to compile and
    fuse deterministic sub-graphs for faster execution.
    """

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
        use_compiler: bool = False,
    ) -> None:
        self.registry = registry or adapter_registry
        self.use_compiler = use_compiler
        self._planner: Any = None

    def _get_planner(self) -> Any:
        """Lazy-load the planner to avoid circular imports."""
        if self._planner is None:
            from omnirag.compiler.planner import SelectiveExecutionPlanner
            self._planner = SelectiveExecutionPlanner(registry=self.registry)
        return self._planner

    def execute(
        self,
        config: PipelineConfig,
        query: str,
        **kwargs: Any,
    ) -> GenerationResult:
        """Execute a pipeline end-to-end.

        If use_compiler is True, deterministic sub-graphs are compiled
        and executed as fused functions.
        """
        dag = PipelineDAG(config)
        start_time = time.monotonic()

        logger.info(
            "pipeline.execute.start",
            pipeline=config.name,
            stages=dag.stage_count,
            strategy=config.execution.strategy,
            compiled=self.use_compiler,
        )

        if self.use_compiler:
            outputs = self._execute_with_compiler(config, dag, query, **kwargs)
        else:
            outputs = self._execute_interpreted(dag, query, **kwargs)

        total_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info("pipeline.execute.complete", pipeline=config.name, duration_ms=total_ms)

        # Return the output of the last stage
        order = dag.topological_sort()
        last_stage_id = order[-1]
        final_output = outputs.get(last_stage_id, "")

        if isinstance(final_output, GenerationResult):
            final_output.metadata["duration_ms"] = total_ms
            return final_output

        return GenerationResult(
            answer=str(final_output),
            confidence=0.5,
            metadata={"pipeline": config.name, "duration_ms": total_ms},
        )

    def _execute_interpreted(
        self,
        dag: PipelineDAG,
        query: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Pure interpreted execution — every stage goes through the full path."""
        execution_order = dag.topological_sort()
        outputs: dict[str, Any] = {"query": query}

        for stage_id in execution_order:
            stage = dag.get_stage(stage_id)
            stage_start = time.monotonic()

            try:
                result = self._execute_stage(stage, outputs, query, **kwargs)
                outputs[stage_id] = result

                logger.info(
                    "stage.execute.complete",
                    stage=stage_id,
                    mode="interpreted",
                    duration_ms=round((time.monotonic() - stage_start) * 1000, 2),
                )
            except Exception as e:
                logger.error("stage.execute.error", stage=stage_id, error=str(e))
                raise StageExecutionError(stage_id, str(e)) from e

        return outputs

    def _execute_with_compiler(
        self,
        config: PipelineConfig,
        dag: PipelineDAG,
        query: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execution with compiler — fuse deterministic sub-graphs."""
        planner = self._get_planner()
        plan = planner.get_execution_plan(config)
        compiled_subgraphs = planner.compile(config)

        outputs: dict[str, Any] = {"query": query}

        for step in plan:
            step_start = time.monotonic()

            if step["type"] == "compiled":
                # Find the matching compiled subgraph
                sg = next(
                    (s for s in compiled_subgraphs if s.subgraph_id == step["subgraph_id"]),
                    None,
                )
                if sg is None:
                    # Fallback to interpreted
                    for sid in step["stages"]:
                        stage = dag.get_stage(sid)
                        outputs[sid] = self._execute_stage(stage, outputs, query, **kwargs)
                    continue

                # Resolve input for the first stage of the subgraph
                first_stage = dag.get_stage(step["stages"][0])
                input_data = None
                if first_stage.input:
                    input_data = outputs.get(first_stage.input, query)

                # Execute the fused subgraph
                result = sg.execute(input_data, query, self.registry, **kwargs)

                # Store output under the last stage ID
                last_stage_id = step["stages"][-1]
                outputs[last_stage_id] = result
                # Also store for intermediate references
                for sid in step["stages"]:
                    outputs[sid] = result

                logger.info(
                    "subgraph.execute.complete",
                    subgraph=step["subgraph_id"],
                    stages=step["stages"],
                    mode="compiled",
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                )
            else:
                # Interpreted stage
                stage_id = step["stages"][0]
                stage = dag.get_stage(stage_id)
                try:
                    result = self._execute_stage(stage, outputs, query, **kwargs)
                    outputs[stage_id] = result

                    logger.info(
                        "stage.execute.complete",
                        stage=stage_id,
                        mode="interpreted",
                        duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    )
                except Exception as e:
                    logger.error("stage.execute.error", stage=stage_id, error=str(e))
                    raise StageExecutionError(stage_id, str(e)) from e

        return outputs

    def _execute_stage(
        self,
        stage: StageConfig,
        outputs: dict[str, Any],
        query: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a single stage."""
        input_data = None
        if stage.input:
            input_data = outputs.get(stage.input)
            if input_data is None and stage.input != "query":
                raise StageExecutionError(
                    stage.id, f"Input '{stage.input}' not found in outputs"
                )

        if stage.adapter and self.registry.has(stage.adapter):
            adapter = self.registry.get(stage.adapter)
            return self._call_adapter(adapter, stage, input_data, query, **kwargs)

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
        raise StageExecutionError(
            stage.id,
            f"Runtime '{stage.runtime}' component execution not yet implemented",
        )
