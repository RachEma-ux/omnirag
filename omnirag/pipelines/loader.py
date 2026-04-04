"""Pipeline YAML loader and validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from omnirag.core.exceptions import PipelineCycleError, PipelineValidationError
from omnirag.pipelines.schema import PipelineConfig


def load_pipeline(source: str | Path) -> PipelineConfig:
    """Load a pipeline from a YAML file or string.

    Args:
        source: File path or YAML string.

    Returns:
        Validated PipelineConfig.

    Raises:
        PipelineValidationError: If the YAML is invalid.
    """
    path = Path(source)
    if path.exists() and path.is_file():
        raw = path.read_text(encoding="utf-8")
    else:
        raw = str(source)

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise PipelineValidationError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise PipelineValidationError("Pipeline YAML must be a mapping (dict)")

    try:
        config = PipelineConfig(**data)
    except ValidationError as e:
        raise PipelineValidationError(f"Pipeline schema validation failed:\n{e}") from e

    errors = validate_pipeline(config)
    if errors:
        raise PipelineValidationError(
            "Pipeline validation errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return config


def validate_pipeline(config: PipelineConfig) -> list[str]:
    """Validate a pipeline config for semantic correctness.

    Checks:
    - Unique stage IDs
    - Valid input references (stage IDs exist)
    - No dependency cycles
    - At least one stage

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    if not config.stages:
        errors.append("Pipeline must have at least one stage")
        return errors

    # Check unique IDs
    ids = config.stage_ids()
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            errors.append(f"Duplicate stage ID: '{sid}'")
        seen.add(sid)

    # Check input references
    valid_refs = seen | {"query"}
    for stage in config.stages:
        if stage.input and stage.input not in valid_refs:
            errors.append(
                f"Stage '{stage.id}' references unknown input '{stage.input}'"
            )
        for dep in stage.depends_on:
            if dep not in seen:
                errors.append(
                    f"Stage '{stage.id}' depends on unknown stage '{dep}'"
                )

    # Check for cycles
    try:
        _detect_cycles(config)
    except PipelineCycleError as e:
        errors.append(str(e))

    # Check strategy validity
    valid_strategies = {"single", "fallback", "ensemble", "vote"}
    if config.execution.strategy not in valid_strategies:
        errors.append(
            f"Unknown strategy '{config.execution.strategy}'. "
            f"Valid: {valid_strategies}"
        )

    return errors


def _detect_cycles(config: PipelineConfig) -> None:
    """Detect cycles in the pipeline DAG using DFS."""
    adjacency: dict[str, list[str]] = {s.id: [] for s in config.stages}

    for stage in config.stages:
        if stage.input and stage.input != "query":
            adjacency.setdefault(stage.input, [])
            adjacency[stage.input].append(stage.id)
        for dep in stage.depends_on:
            adjacency.setdefault(dep, [])
            adjacency[dep].append(stage.id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in adjacency}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if color.get(neighbor) == GRAY:
                raise PipelineCycleError(
                    f"Cycle detected involving stages: {node} -> {neighbor}"
                )
            if color.get(neighbor) == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for node in adjacency:
        if color[node] == WHITE:
            dfs(node)
