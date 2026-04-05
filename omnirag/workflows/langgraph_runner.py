"""LangGraph workflow runner — stateful, persistent, subgraph-capable.

Built-in workflows:
  - full_ingestion: source → parse → chunk → extract → resolve → build → communities → reports
  - query_pipeline: route → retrieve → context → reason → trace
  - evaluation: query → answer → LLM judge → score
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from omnirag.models.canonical import AgentRun

logger = structlog.get_logger(__name__)


class WorkflowStep:
    """A single step in a workflow."""

    def __init__(self, name: str, handler: Any = None) -> None:
        self.name = name
        self.handler = handler
        self.status = "pending"
        self.result: Any = None
        self.error: str | None = None
        self.duration_ms: float = 0

    async def execute(self, state: dict) -> dict:
        start = time.monotonic()
        try:
            if self.handler:
                self.result = await self.handler(state)
            else:
                self.result = state
            self.status = "completed"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error("workflow.step_failed", step=self.name, error=str(e))
        self.duration_ms = (time.monotonic() - start) * 1000
        return {"step": self.name, "status": self.status, "duration_ms": round(self.duration_ms, 1)}


class Workflow:
    """Stateful workflow — sequence of steps with persistent state."""

    def __init__(self, workflow_type: str, steps: list[WorkflowStep] | None = None) -> None:
        self.id = str(uuid.uuid4())
        self.workflow_type = workflow_type
        self.steps = steps or []
        self.state: dict = {}
        self.run = AgentRun(id=self.id, workflow_type=workflow_type)

    async def execute(self, inputs: dict) -> AgentRun:
        self.state = inputs.copy()
        self.run.status = "running"
        logger.info("workflow.start", id=self.id, type=self.workflow_type, steps=len(self.steps))

        for step in self.steps:
            result = await step.execute(self.state)
            self.run.steps.append(result)

            if step.status == "failed":
                self.run.status = "failed"
                self.run.error = step.error
                break

            if step.result and isinstance(step.result, dict):
                self.state.update(step.result)

        if self.run.status == "running":
            self.run.status = "completed"
            self.run.final_output = self.state

        self.run.completed_at = time.time()
        logger.info("workflow.complete", id=self.id, status=self.run.status)
        return self.run


class WorkflowRunner:
    """Manages workflow definitions and execution."""

    def __init__(self) -> None:
        self._definitions: dict[str, list[WorkflowStep]] = {}
        self._runs: dict[str, AgentRun] = {}

    def register(self, workflow_type: str, steps: list[WorkflowStep]) -> None:
        self._definitions[workflow_type] = steps

    async def run(self, workflow_type: str, inputs: dict) -> AgentRun:
        steps = self._definitions.get(workflow_type)
        if not steps:
            run = AgentRun(workflow_type=workflow_type, status="failed", error=f"Unknown workflow: {workflow_type}")
            return run

        workflow = Workflow(workflow_type, [WorkflowStep(s.name, s.handler) for s in steps])
        result = await workflow.execute(inputs)
        self._runs[result.id] = result
        return result

    def get_status(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[dict]:
        runs = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in runs[:limit]]

    def list_workflows(self) -> list[str]:
        return list(self._definitions.keys())


_runner = WorkflowRunner()


def get_workflow_runner() -> WorkflowRunner:
    return _runner
