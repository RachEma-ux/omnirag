"""Async task manager for pipeline invocations.

Stores task state in memory. Production use should swap for
Redis/PostgreSQL-backed storage.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str
    query: str
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


class TaskManager:
    """In-memory async task manager."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, pipeline_name: str, query: str) -> TaskRecord:
        task = TaskRecord(pipeline_name=pipeline_name, query=query)
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def update(
        self,
        task_id: str,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            task.result = result
            task.error = error
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = time.time()

    def list_tasks(self, limit: int = 50) -> list[TaskRecord]:
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )[:limit]


# Global singleton
task_manager = TaskManager()
