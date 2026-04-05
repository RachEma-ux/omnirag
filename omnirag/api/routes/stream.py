"""WebSocket streaming — /v1/stream with token + citation events."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from omnirag.output.retrieval.hybrid import get_retriever
from omnirag.output.generation.engine import build_prompt, extract_citations, get_generation_engine

router = APIRouter(prefix="/v1")

# Track active connections per user
_active_streams: dict[str, int] = {}
MAX_CONCURRENT_STREAMS = 10


@router.websocket("/stream")
async def stream(ws: WebSocket):
    """WebSocket streaming: tokens + citations in real-time.

    Client sends: {"query": "...", "top_k": 10}
    Server sends:
      {"type": "token", "data": "..."}
      {"type": "citation", "data": {"doc_id": "...", "chunk_id": "...", "snippet": "..."}}
      {"type": "end", "data": {"total_tokens": N, "latency_ms": N}}
    """
    await ws.accept()
    user = "anonymous"

    try:
        # Receive query
        raw = await ws.receive_text()
        msg = json.loads(raw)
        query = msg.get("query", "")
        top_k = msg.get("top_k", 10)

        if not query:
            await ws.send_json({"type": "error", "data": "query is required"})
            await ws.close()
            return

        # Rate limit
        _active_streams[user] = _active_streams.get(user, 0) + 1
        if _active_streams[user] > MAX_CONCURRENT_STREAMS:
            await ws.send_json({"type": "error", "data": "max concurrent streams exceeded"})
            _active_streams[user] -= 1
            await ws.close()
            return

        start = time.monotonic()

        # Retrieve
        retriever = get_retriever()
        evidence = await retriever.retrieve(query=query, acl_principals=["public"], top_k=top_k)

        if not evidence.chunks:
            await ws.send_json({"type": "token", "data": "No relevant chunks found."})
            await ws.send_json({"type": "end", "data": {"total_tokens": 0, "latency_ms": 0}})
            await ws.close()
            return

        # Generate (non-streaming — send answer in word-sized tokens for streaming feel)
        engine = get_generation_engine()
        gen_result = await engine.generate(query, evidence.chunks)

        # Stream tokens (word by word)
        words = gen_result.answer.split()
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await ws.send_json({"type": "token", "data": token})

        # Send citations
        for citation in gen_result.citations:
            await ws.send_json({
                "type": "citation",
                "data": {
                    "doc_id": citation.doc_id,
                    "chunk_id": citation.chunk_id,
                    "snippet": citation.snippet,
                },
            })

        # End
        latency = (time.monotonic() - start) * 1000
        await ws.send_json({
            "type": "end",
            "data": {"total_tokens": gen_result.tokens, "latency_ms": round(latency, 1)},
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
    finally:
        _active_streams[user] = max(0, _active_streams.get(user, 1) - 1)
        try:
            await ws.close()
        except Exception:
            pass
