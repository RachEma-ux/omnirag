"""Tests for the Selective Execution Planner (compiler)."""

from omnirag.adapters.chunking import RecursiveChunkerAdapter
from omnirag.adapters.ingestion import FileLoaderAdapter
from omnirag.adapters.memory import MemoryVectorAdapter
from omnirag.adapters.registry import AdapterRegistry
from omnirag.compiler.planner import SelectiveExecutionPlanner
from omnirag.pipelines.schema import PipelineConfig, StageConfig


def _registry_with_defaults() -> AdapterRegistry:
    reg = AdapterRegistry()
    reg.register("file_loader", FileLoaderAdapter)
    reg.register("recursive_splitter", RecursiveChunkerAdapter)
    reg.register("memory", MemoryVectorAdapter)
    return reg


def _pipeline_with_mixed_stages() -> PipelineConfig:
    """Pipeline with deterministic (chunking, retrieval) and non-deterministic (generation) stages."""
    return PipelineConfig(
        name="mixed_test",
        stages=[
            StageConfig(id="load", adapter="file_loader"),
            StageConfig(id="chunk", adapter="recursive_splitter", input="load"),
            StageConfig(id="store", adapter="memory", input="chunk", params={"mode": "upsert"}),
            StageConfig(id="retrieve", adapter="memory", input="query"),
            # generation would be non-deterministic but we don't register it
            StageConfig(id="generate", adapter="llm_gen", input="retrieve"),
        ],
    )


def _pipeline_all_deterministic() -> PipelineConfig:
    return PipelineConfig(
        name="all_det",
        stages=[
            StageConfig(id="load", adapter="file_loader"),
            StageConfig(id="chunk", adapter="recursive_splitter", input="load"),
            StageConfig(id="store", adapter="memory", input="chunk"),
        ],
    )


def test_analyze_identifies_deterministic():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_with_mixed_stages()
    result = planner.analyze(config)

    # file_loader=ingestion(det), recursive_splitter=chunking(det),
    # memory=retrieval(det), llm_gen=not registered(non-det)
    assert result["load"] is True
    assert result["chunk"] is True
    assert result["store"] is True
    assert result["retrieve"] is True
    assert result["generate"] is False


def test_find_subgraphs():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_with_mixed_stages()
    subgraphs = planner.find_subgraphs(config)

    # Should find at least one subgraph of consecutive deterministic stages
    assert len(subgraphs) >= 1
    # The first subgraph should contain load, chunk, store, retrieve (4 stages)
    assert len(subgraphs[0]) >= 2


def test_find_subgraphs_all_deterministic():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_all_deterministic()
    subgraphs = planner.find_subgraphs(config)

    assert len(subgraphs) == 1
    assert subgraphs[0] == ["load", "chunk", "store"]


def test_compile_caches():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_all_deterministic()

    first = planner.compile(config)
    second = planner.compile(config)

    # Should be the same cached object
    assert first is second


def test_compile_returns_subgraphs():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_all_deterministic()
    compiled = planner.compile(config)

    assert len(compiled) == 1
    assert compiled[0].stage_ids == ["load", "chunk", "store"]
    assert compiled[0].subgraph_id == "all_det_sg0"


def test_execution_plan_mixed():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_with_mixed_stages()
    plan = planner.get_execution_plan(config)

    # Should have compiled step(s) + an interpreted step for "generate"
    types = [step["type"] for step in plan]
    assert "interpreted" in types  # generate is interpreted


def test_invalidate_cache():
    reg = _registry_with_defaults()
    planner = SelectiveExecutionPlanner(registry=reg)
    config = _pipeline_all_deterministic()

    planner.compile(config)
    assert len(planner._cache) > 0

    planner.invalidate()
    assert len(planner._cache) == 0


def test_pipeline_hash_stability():
    """Same config should produce the same hash."""
    config = _pipeline_all_deterministic()
    h1 = SelectiveExecutionPlanner._hash_pipeline(config)
    h2 = SelectiveExecutionPlanner._hash_pipeline(config)
    assert h1 == h2
