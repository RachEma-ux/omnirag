"""Graph WebSocket — real-time collaboration for knowledge graph visualization (V7)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

router = APIRouter()

# Session store: session_id → list of connected websockets
_sessions: dict[str, list[dict]] = {}


@router.websocket("/ws/graph")
async def graph_collaboration(ws: WebSocket):
    """Real-time graph collaboration: shared viewport, selections, cursors."""
    await ws.accept()
    session_id = ws.query_params.get("session", "default")
    user_id = ws.query_params.get("user", f"user-{uuid.uuid4().hex[:6]}")

    client = {"ws": ws, "user_id": user_id}
    _sessions.setdefault(session_id, []).append(client)

    # Notify others
    await broadcast(session_id, {"type": "join", "user": user_id, "count": len(_sessions[session_id])}, exclude=ws)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg["user"] = user_id
            # Broadcast to all others in session
            await broadcast(session_id, msg, exclude=ws)
    except WebSocketDisconnect:
        logger.debug("graph_ws.client_disconnected", user=user_id)
    except Exception as e:
        logger.debug("graph_ws.receive_error", user=user_id, error=str(e))
    finally:
        _sessions[session_id] = [c for c in _sessions.get(session_id, []) if c["ws"] != ws]
        await broadcast(session_id, {"type": "leave", "user": user_id, "count": len(_sessions.get(session_id, []))})
        try:
            await ws.close()
        except Exception:
            pass


async def broadcast(session_id: str, msg: dict, exclude: Any = None) -> None:
    """Send message to all clients in a session except the sender."""
    data = json.dumps(msg)
    for client in _sessions.get(session_id, []):
        if client["ws"] == exclude:
            continue
        try:
            await client["ws"].send_text(data)
        except Exception:
            pass


@router.get("/ws/graph/sessions")
async def list_sessions():
    """List active collaboration sessions."""
    return {
        session_id: {"users": [c["user_id"] for c in clients], "count": len(clients)}
        for session_id, clients in _sessions.items() if clients
    }
