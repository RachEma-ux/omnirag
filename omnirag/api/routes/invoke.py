"""Pipeline invocation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from omnirag.api.routes.pipelines import _pipelines
from omnirag.core.exceptions import ExecutionError
from omnirag.core.models import GenerationResult
from omnirag.pipelines.executor import InterpretedExecutor

router = APIRouter()


class InvokeRequest(BaseModel):
    """Request body for pipeline invocation."""
    query: str
    params: dict[str, object] = {}

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What is Retrieval-Augmented Generation?",
                    "params": {}
                },
                {
                    "query": "Summarize the key findings from the uploaded documents",
                    "params": {"top_k": 5, "temperature": 0.7}
                }
            ]
        }
    }


class InvokeResponse(BaseModel):
    """Response from pipeline invocation."""
    answer: str
    citations: list[str]
    confidence: float
    metadata: dict[str, object]


@router.post("/pipelines/{name}/invoke", response_model=InvokeResponse)
async def invoke_pipeline(name: str, body: InvokeRequest) -> InvokeResponse:
    """Execute a pipeline synchronously."""
    config = _pipelines.get(name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    executor = InterpretedExecutor()

    try:
        result: GenerationResult = executor.execute(config, body.query)
    except ExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return InvokeResponse(
        answer=result.answer,
        citations=result.citations,
        confidence=result.confidence,
        metadata=result.metadata,
    )
