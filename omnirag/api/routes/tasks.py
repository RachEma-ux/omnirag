"""Async task endpoints — submit pipelines for background execution."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from omnirag.api.routes.pipelines import _pipelines
from omnirag.api.tasks import TaskStatus, task_manager
from omnirag.core.exceptions import ExecutionError
from omnirag.pipelines.executor import InterpretedExecutor

router = APIRouter()


class AsyncInvokeRequest(BaseModel):
    query: str
    params: dict[str, Any] = {}
    use_compiler: bool = False


class TaskResponse(BaseModel):
    task_id: str
    status: str
    pipeline_name: str


class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    pipeline_name: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float
    completed_at: float | None = None


@router.post(
    "/pipelines/{name}/invoke_async",
    response_model=TaskResponse,
)
async def invoke_pipeline_async(
    name: str, body: AsyncInvokeRequest
) -> TaskResponse:
    """Submit a pipeline for async execution. Returns a task ID."""
    config = _pipelines.get(name)
    if config is None:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{name}' not found"
        )

    task = task_manager.create(pipeline_name=name, query=body.query)

    # Run in background
    asyncio.get_event_loop().run_in_executor(
        None,
        _run_task,
        task.task_id,
        name,
        body.query,
        body.use_compiler,
    )

    return TaskResponse(
        task_id=task.task_id,
        status=task.status.value,
        pipeline_name=name,
    )


@router.get("/tasks/{task_id}", response_model=TaskResultResponse)
async def get_task_result(task_id: str) -> TaskResultResponse:
    """Poll for task result."""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Task '{task_id}' not found"
        )

    return TaskResultResponse(
        task_id=task.task_id,
        status=task.status.value,
        pipeline_name=task.pipeline_name,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks() -> list[TaskResponse]:
    """List recent tasks."""
    return [
        TaskResponse(
            task_id=t.task_id,
            status=t.status.value,
            pipeline_name=t.pipeline_name,
        )
        for t in task_manager.list_tasks()
    ]


def _run_task(
    task_id: str,
    pipeline_name: str,
    query: str,
    use_compiler: bool,
) -> None:
    """Execute pipeline in background thread."""
    task_manager.update(task_id, TaskStatus.RUNNING)

    config = _pipelines.get(pipeline_name)
    if config is None:
        task_manager.update(
            task_id, TaskStatus.FAILED, error="Pipeline not found"
        )
        return

    executor = InterpretedExecutor(use_compiler=use_compiler)

    try:
        result = executor.execute(config, query)
        task_manager.update(
            task_id,
            TaskStatus.COMPLETED,
            result=result.model_dump(),
        )
    except ExecutionError as e:
        task_manager.update(
            task_id, TaskStatus.FAILED, error=str(e)
        )
