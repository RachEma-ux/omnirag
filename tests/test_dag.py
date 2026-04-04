"""Tests for pipeline DAG."""

from omnirag.pipelines.dag import PipelineDAG
from omnirag.pipelines.schema import PipelineConfig, StageConfig


def _make_config(stages: list[StageConfig]) -> PipelineConfig:
    return PipelineConfig(name="test", stages=stages)


def test_topological_sort_linear():
    config = _make_config([
        StageConfig(id="a", adapter="x"),
        StageConfig(id="b", adapter="y", input="a"),
        StageConfig(id="c", adapter="z", input="b"),
    ])
    dag = PipelineDAG(config)
    order = dag.topological_sort()
    assert order.index("a") < order.index("b") < order.index("c")


def test_topological_sort_parallel():
    config = _make_config([
        StageConfig(id="root", adapter="x"),
        StageConfig(id="left", adapter="y", input="root"),
        StageConfig(id="right", adapter="z", input="root"),
        StageConfig(id="merge", adapter="w", depends_on=["left", "right"]),
    ])
    dag = PipelineDAG(config)
    order = dag.topological_sort()
    assert order.index("root") < order.index("left")
    assert order.index("root") < order.index("right")
    assert order.index("left") < order.index("merge")
    assert order.index("right") < order.index("merge")


def test_root_and_leaf_stages():
    config = _make_config([
        StageConfig(id="a", adapter="x"),
        StageConfig(id="b", adapter="y", input="a"),
    ])
    dag = PipelineDAG(config)
    assert dag.root_stages() == ["a"]
    assert dag.leaf_stages() == ["b"]


def test_stage_count():
    config = _make_config([
        StageConfig(id="a", adapter="x"),
        StageConfig(id="b", adapter="y"),
    ])
    dag = PipelineDAG(config)
    assert dag.stage_count == 2
