"""GraphRAG API — 4 endpoints: local, global, drift, route."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from omnirag.graphrag.query.local import local_search
from omnirag.graphrag.query.global_search import global_search
from omnirag.graphrag.query.drift import drift_search
from omnirag.graphrag.router.router import get_query_router
from omnirag.graphrag.cache import get_graph_cache
from omnirag.graphrag.metrics import get_graphrag_metrics
from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.incremental import get_incremental_engine
from omnirag.graphrag.models import QueryMode
from omnirag.output.generation.engine import get_generation_engine

router = APIRouter(prefix="/graphrag")


class GraphQueryRequest(BaseModel):
    query: str
    user_principal: str = "public"
    options: dict = {}

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "How is OmniRAG related to Neo4j?", "user_principal": "user:alice"},
                {"query": "Summarize all themes across the corpus", "user_principal": "user:alice"},
            ]
        }
    }


async def _run_search(mode: QueryMode, query: str, acl: list[str], options: dict) -> dict:
    """Execute search by mode, with caching + metrics."""
    cache = get_graph_cache()
    metrics = get_graphrag_metrics()
    start = time.monotonic()

    # Check cache
    cached = cache.get(mode, query, acl)
    if cached:
        metrics.cache_hit.inc(mode.value)
        return {
            "evidence": cached.to_dict(),
            "cache_hit": True,
            "mode": mode.value,
        }

    # Execute
    if mode == QueryMode.LOCAL:
        evidence = await local_search(query, acl, max_hops=options.get("max_hops", 2))
    elif mode == QueryMode.GLOBAL:
        evidence = await global_search(query, acl)
    elif mode == QueryMode.DRIFT:
        evidence = await drift_search(query, acl, max_hops=options.get("max_hops", 2))
    else:
        evidence = await local_search(query, acl)

    # Generate answer from evidence chunks
    engine = get_generation_engine()
    from omnirag.output.retrieval.hybrid import RetrievalResult
    chunks_for_gen = [
        RetrievalResult(
            chunk_id=c.get("chunk_id", ""), doc_id=c.get("doc_id", ""),
            content=c.get("content", c.get("text", "")), score=1.0,
        )
        for c in evidence.chunks if c.get("content") or c.get("text")
    ]

    gen_result = None
    if chunks_for_gen:
        gen_result = await engine.generate(query, chunks_for_gen)

    # Cache result
    cache.put(mode, query, acl, evidence)

    # Metrics
    elapsed = time.monotonic() - start
    metrics.query_latency.observe(elapsed)
    metrics.retrieval_confidence.set(evidence.confidence)
    metrics.retrieval_coverage.set(evidence.coverage)

    result = {
        "answer": gen_result.answer if gen_result else "No relevant evidence found.",
        "citations": [{"doc_id": c.doc_id, "chunk_id": c.chunk_id, "snippet": c.snippet}
                       for c in (gen_result.citations if gen_result else [])],
        "evidence": evidence.to_dict(),
        "cache_hit": False,
        "mode": mode.value,
        "latency_ms": round(elapsed * 1000, 1),
    }
    return result


@router.post("/query/local", tags=["graphrag"])
async def query_local(body: GraphQueryRequest, request: Request):
    """Entity-centric graph search."""
    acl = [body.user_principal] + getattr(request.state, "user_principals", ["public"])
    result = await _run_search(QueryMode.LOCAL, body.query, acl, body.options)
    return JSONResponse(content=result, headers={
        "X-Cache-Status": "HIT" if result["cache_hit"] else "MISS",
        "X-Mode-Used": "local",
    })


@router.post("/query/global", tags=["graphrag"])
async def query_global(body: GraphQueryRequest, request: Request):
    """Map-reduce over community reports."""
    acl = [body.user_principal] + getattr(request.state, "user_principals", ["public"])
    result = await _run_search(QueryMode.GLOBAL, body.query, acl, body.options)
    return JSONResponse(content=result, headers={
        "X-Cache-Status": "HIT" if result["cache_hit"] else "MISS",
        "X-Mode-Used": "global",
    })


@router.post("/query/drift", tags=["graphrag"])
async def query_drift(body: GraphQueryRequest, request: Request):
    """DRIFT: global → extract entities → local refinement."""
    acl = [body.user_principal] + getattr(request.state, "user_principals", ["public"])
    result = await _run_search(QueryMode.DRIFT, body.query, acl, body.options)
    return JSONResponse(content=result, headers={
        "X-Cache-Status": "HIT" if result["cache_hit"] else "MISS",
        "X-Mode-Used": "drift",
    })


@router.post("/query/route", tags=["graphrag"])
async def query_route(body: GraphQueryRequest):
    """Auto-route: returns recommended mode + confidence."""
    router_instance = get_query_router()
    decision = router_instance.route(body.query)
    return {
        "mode": decision.mode.value,
        "confidence": decision.confidence,
        "stage": decision.stage,
    }


@router.get("/stats", tags=["graphrag"])
async def graph_stats():
    """Graph store stats + cache + metrics."""
    return {
        "graph": get_graph_store().stats(),
        "cache": get_graph_cache().get_stats(),
        "metrics": get_graphrag_metrics().to_dict(),
        "stale_communities": get_incremental_engine().get_stale_count(),
        "incremental_stats": get_incremental_engine().stats,
    }
