"""Search API — POST /v1/search, POST /v1/search/debug."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from omnirag.output.retrieval.hybrid import get_retriever
from omnirag.output.generation.engine import get_generation_engine
from omnirag.output.consistency import get_consistency_coordinator

router = APIRouter(prefix="/v1")


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: dict | None = None
    read_your_writes: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "What are the compliance requirements?", "top_k": 10},
                {"query": "Explain RAG architecture", "top_k": 5, "filters": {"doc_id": ["uuid1"]}},
            ]
        }
    }


@router.post("/search", tags=["search"])
async def search(body: SearchRequest, request: Request):
    """Full pipeline: ACL filter → hybrid search → rerank → generate → respond."""
    start = time.monotonic()

    # Extract user principals (from middleware or default)
    user_principals = getattr(request.state, "user_principals", ["public"])
    user_hash = getattr(request.state, "user_hash", "anonymous")

    # Consistency check
    coordinator = get_consistency_coordinator()
    consistency = "strong"
    if body.read_your_writes:
        user_version = coordinator.get_user_version(user_hash)
        consistency = await coordinator.wait_for_consistency(user_version)

    # Retrieve
    retriever = get_retriever()
    evidence = await retriever.retrieve(
        query=body.query,
        acl_principals=user_principals,
        top_k=body.top_k,
        filters=body.filters,
    )

    if evidence.mode == "unavailable":
        return JSONResponse(
            status_code=503,
            content={"error": "All retrieval backends unavailable"},
            headers={"Retry-After": "5"},
        )

    # Generate
    engine = get_generation_engine()
    gen_result = await engine.generate(body.query, evidence.chunks)

    total_ms = (time.monotonic() - start) * 1000

    headers = {"X-Consistency": consistency}
    if evidence.fallback_used:
        headers["X-Fallback"] = evidence.fallback_reason or "true"

    return JSONResponse(
        content={
            "answer": gen_result.answer,
            "citations": [
                {
                    "doc_id": c.doc_id,
                    "chunk_id": c.chunk_id,
                    "snippet": c.snippet,
                    "relevance_score": c.relevance_score,
                }
                for c in gen_result.citations
            ],
            "metadata": {
                "mode": evidence.mode,
                "retrieval_latency_ms": round(evidence.latency_ms, 1),
                "generation_latency_ms": round(gen_result.latency_ms, 1),
                "total_latency_ms": round(total_ms, 1),
                "consistency": consistency,
                "chunks_retrieved": len(evidence.chunks),
                "model": gen_result.model,
            },
        },
        headers=headers,
    )


@router.post("/search/debug", tags=["search"])
async def search_debug(body: SearchRequest, request: Request):
    """Returns intermediate retrieval results (admin only)."""
    user_principals = getattr(request.state, "user_principals", ["public"])

    retriever = get_retriever()
    evidence = await retriever.retrieve(
        query=body.query, acl_principals=user_principals,
        top_k=body.top_k, filters=body.filters,
    )

    return {
        "mode": evidence.mode,
        "fallback_used": evidence.fallback_used,
        "fallback_reason": evidence.fallback_reason,
        "latency_ms": round(evidence.latency_ms, 1),
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "content_preview": c.content[:200],
                "score": c.score,
                "retrieval_scores": c.retrieval_scores,
            }
            for c in evidence.chunks
        ],
    }
