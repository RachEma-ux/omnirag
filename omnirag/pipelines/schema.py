"""YAML pipeline schema definition and validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage."""

    id: str
    runtime: str = "shared"  # "shared", "langchain", "llamaindex", "haystack"
    adapter: str | None = None  # adapter name from registry
    component: str | None = None  # native runtime component
    params: dict[str, Any] = Field(default_factory=dict)
    input: str | None = None  # stage ID or "query" for initial input
    depends_on: list[str] = Field(default_factory=list)
    output: str | None = None  # expected output type


class ExecutionConfig(BaseModel):
    """Execution strategy configuration."""

    strategy: str = "single"  # single, fallback, ensemble, vote
    fallback_condition: str | None = None
    ensemble_merge: str = "deduplicate"  # deduplicate, concat, rerank
    parallelism: int = 1


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration parsed from YAML."""

    version: str = "4.0"
    name: str
    description: str = ""
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    stages: list[StageConfig]
    output: str = "GenerationResult"

    def get_stage(self, stage_id: str) -> StageConfig | None:
        """Get a stage by its ID."""
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        return None

    def stage_ids(self) -> list[str]:
        """Get all stage IDs in order."""
        return [s.id for s in self.stages]


# JSON Schema for external validation tools
PIPELINE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "stages"],
    "properties": {
        "version": {"type": "string", "default": "4.0"},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "execution": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["single", "fallback", "ensemble", "vote"],
                },
                "fallback_condition": {"type": "string"},
                "ensemble_merge": {
                    "type": "string",
                    "enum": ["deduplicate", "concat", "rerank"],
                },
                "parallelism": {"type": "integer", "minimum": 1},
            },
        },
        "stages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string"},
                    "runtime": {"type": "string"},
                    "adapter": {"type": "string"},
                    "component": {"type": "string"},
                    "params": {"type": "object"},
                    "input": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "output": {"type": "string"},
                },
            },
        },
        "output": {"type": "string"},
    },
}
