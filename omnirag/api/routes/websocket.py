"""WebSocket endpoint for real-time streaming pipeline execution."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import structlog

from omnirag.api.routes.pipelines import _pipelines
from omnirag.core.exceptions import ExecutionError
from omnirag.pipelines.executor import InterpretedExecutor

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket) -> None:
    """WebSocket endpoint for streaming pipeline execution.

    Client sends:
        {"pipeline": "name", "query": "...", "use_compiler": false}

    Server streams back:
        {"type": "stage", "stage_id": "...", "status": "start"}
        {"type": "stage", "stage_id": "...", "status": "complete", "duration_ms": ...}
        {"type": "result", "answer": "...", "confidence": ..., "citations": [...]}
        {"type": "error", "message": "..."}
    """
    await ws.accept()

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            pipeline_name = msg.get("pipeline", "")
            query = msg.get("query", "")
            use_compiler = msg.get("use_compiler", False)

            if not pipeline_name or not query:
                await ws.send_json({
                    "type": "error",
                    "message": "Both 'pipeline' and 'query' are required",
                })
                continue

            config = _pipelines.get(pipeline_name)
            if config is None:
                await ws.send_json({
                    "type": "error",
                    "message": f"Pipeline '{pipeline_name}' not found",
                })
                continue

            await _stream_execution(ws, config, query, use_compiler)

    except WebSocketDisconnect:
        logger.info("websocket.disconnected")


async def _stream_execution(
    ws: WebSocket,
    config: Any,
    query: str,
    use_compiler: bool,
) -> None:
    """Execute pipeline and stream stage progress to WebSocket."""
    from omnirag.pipelines.dag import PipelineDAG

    dag = PipelineDAG(config)
    executor = InterpretedExecutor(use_compiler=use_compiler)
    order = dag.topological_sort()

    await ws.send_json({
        "type": "pipeline_start",
        "pipeline": config.name,
        "stages": order,
    })

    start = time.monotonic()

    try:
        result = executor.execute(config, query)

        total_ms = round((time.monotonic() - start) * 1000, 2)

        await ws.send_json({
            "type": "result",
            "answer": result.answer,
            "confidence": result.confidence,
            "citations": result.citations,
            "metadata": {
                **result.metadata,
                "duration_ms": total_ms,
            },
        })
    except ExecutionError as e:
        await ws.send_json({
            "type": "error",
            "message": str(e),
        })
