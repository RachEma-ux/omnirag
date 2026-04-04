"""Pipeline management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from omnirag.core.exceptions import PipelineValidationError
from omnirag.pipelines.loader import load_pipeline
from omnirag.pipelines.schema import PipelineConfig

router = APIRouter()

# In-memory pipeline store (will be replaced with persistent storage)
_pipelines: dict[str, PipelineConfig] = {}


class PipelineUpload(BaseModel):
    """Request body for uploading a pipeline."""
    yaml_content: str


class PipelineResponse(BaseModel):
    """Response for pipeline info."""
    name: str
    description: str
    version: str
    stage_count: int
    strategy: str


@router.post("/", response_model=PipelineResponse)
async def upload_pipeline(body: PipelineUpload) -> PipelineResponse:
    """Upload and register a pipeline from YAML."""
    try:
        config = load_pipeline(body.yaml_content)
    except PipelineValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _pipelines[config.name] = config

    return PipelineResponse(
        name=config.name,
        description=config.description,
        version=config.version,
        stage_count=len(config.stages),
        strategy=config.execution.strategy,
    )


@router.get("/{name}", response_model=PipelineResponse)
async def get_pipeline(name: str) -> PipelineResponse:
    """Get pipeline info by name."""
    config = _pipelines.get(name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    return PipelineResponse(
        name=config.name,
        description=config.description,
        version=config.version,
        stage_count=len(config.stages),
        strategy=config.execution.strategy,
    )


@router.get("/", response_model=list[PipelineResponse])
async def list_pipelines() -> list[PipelineResponse]:
    """List all registered pipelines."""
    return [
        PipelineResponse(
            name=c.name,
            description=c.description,
            version=c.version,
            stage_count=len(c.stages),
            strategy=c.execution.strategy,
        )
        for c in _pipelines.values()
    ]
