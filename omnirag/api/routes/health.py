"""Health and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from omnirag import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@router.get("/ports")
async def ports() -> dict:
    """Port registry — all service port assignments."""
    from omnirag.config.ports import get_all
    return {"ports": get_all(), "range": "8100-8199"}


@router.post("/demo/load")
async def load_demo():
    """Load the Christmas Carol demo — runs full pipeline inside the server process."""
    import os
    from pathlib import Path

    from omnirag.intake.gate import get_gate
    from omnirag.output.index_writers.base import get_writer_registry
    from omnirag.output.embedding import get_embedding_pipeline
    from omnirag.graphrag.projection import get_projection_service
    from omnirag.graphrag.store import get_graph_store

    # Find the text file
    txt = Path(__file__).parent.parent.parent.parent / "examples" / "christmas-carol" / "christmas_carol.txt"
    if not txt.exists():
        # Try tmp
        txt = Path("/data/data/com.termux/files/usr/tmp/christmas_carol.txt")
    if not txt.exists():
        return {"error": "christmas_carol.txt not found. Download: curl -sL https://www.gutenberg.org/cache/epub/24022/pg24022.txt -o examples/christmas-carol/christmas_carol.txt"}

    # 1. Ingest
    gate = get_gate()
    job = await gate.ingest(str(txt), {})
    if job.state.value != "active":
        return {"error": f"Intake failed: {job.errors}", "state": job.state.value}

    chunks = gate.get_chunks(job.id)
    docs = gate.get_documents(job.id)

    # 2. Embed + Index
    pipeline = get_embedding_pipeline()
    results = await pipeline.embed_chunks(chunks)
    registry = get_writer_registry()
    for writer in registry.all():
        await writer.write(chunks, results)

    # 3. Graph projection
    projector = get_projection_service()
    stats = await projector.project(docs, chunks)

    store = get_graph_store()
    return {
        "status": "loaded",
        "intake": {"files": job.files_found, "docs": job.documents_created, "chunks": job.chunks_created},
        "embeddings": len([r for r in results if r.status == "completed"]),
        "graph": store.stats(),
        "projection": stats,
    }


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    """Basic metrics endpoint (Prometheus integration planned)."""
    return {
        "version": __version__,
        "pipelines_loaded": 0,
        "total_invocations": 0,
    }
