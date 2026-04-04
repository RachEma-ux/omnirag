"""Tests for pipeline YAML loader."""

import pytest

from omnirag.core.exceptions import PipelineValidationError
from omnirag.pipelines.loader import load_pipeline, validate_pipeline
from omnirag.pipelines.schema import PipelineConfig, StageConfig


VALID_YAML = """
name: test_pipeline
description: A test pipeline
execution:
  strategy: single
stages:
  - id: load
    adapter: loader
    params:
      path: ./data
  - id: embed
    adapter: embedder
    input: load
  - id: retrieve
    adapter: memory
    input: embed
"""

CYCLE_YAML = """
name: cycle_test
stages:
  - id: a
    adapter: x
    input: b
  - id: b
    adapter: y
    input: a
"""

DUPLICATE_ID_YAML = """
name: dup_test
stages:
  - id: step1
    adapter: x
  - id: step1
    adapter: y
"""


def test_load_valid_yaml():
    config = load_pipeline(VALID_YAML)
    assert config.name == "test_pipeline"
    assert len(config.stages) == 3
    assert config.execution.strategy == "single"


def test_load_detects_cycle():
    with pytest.raises(PipelineValidationError, match="Cycle"):
        load_pipeline(CYCLE_YAML)


def test_load_detects_duplicate_ids():
    with pytest.raises(PipelineValidationError, match="Duplicate"):
        load_pipeline(DUPLICATE_ID_YAML)


def test_validate_unknown_input_ref():
    config = PipelineConfig(
        name="test",
        stages=[
            StageConfig(id="s1", adapter="x", input="nonexistent"),
        ],
    )
    errors = validate_pipeline(config)
    assert any("unknown input" in e for e in errors)


def test_validate_empty_pipeline():
    config = PipelineConfig(name="empty", stages=[])
    errors = validate_pipeline(config)
    assert any("at least one stage" in e for e in errors)


def test_validate_valid_pipeline():
    config = PipelineConfig(
        name="ok",
        stages=[
            StageConfig(id="s1", adapter="x"),
            StageConfig(id="s2", adapter="y", input="s1"),
        ],
    )
    errors = validate_pipeline(config)
    assert errors == []
