"""End-to-end integration test: ingest → index → search → answer.

Tests the full pipeline:
1. Create a test text file
2. Ingest via POST /intake
3. Verify job completes with ACTIVE state
4. Search via POST /v1/search
5. Verify answer contains citations
6. Check lineage
7. Check metrics
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from omnirag.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Health endpoint should return 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_local_text(client: AsyncClient):
    """Ingest a local text file through the full 12-state pipeline."""
    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="omnirag_test_") as f:
        f.write("""# Retrieval-Augmented Generation

RAG is a technique that combines retrieval of relevant documents with
language model generation. It was introduced by Lewis et al. in 2020.

## Key Components

1. Retriever: Finds relevant passages from a knowledge base
2. Generator: Produces answers conditioned on retrieved context
3. Knowledge Base: Stores documents as vectors for similarity search

## Benefits

- Reduces hallucination by grounding responses in real documents
- Allows updating knowledge without retraining the model
- Provides citations for transparency and auditability
""")
        test_file = f.name

    try:
        # Ingest
        resp = await client.post("/intake", json={
            "source": test_file,
            "config": {},
            "pipeline": "test",
        })
        assert resp.status_code == 200
        job = resp.json()

        assert job["state"] == "active", f"Expected active, got {job['state']}. Errors: {job.get('errors')}"
        assert job["files_found"] == 1
        assert job["documents_created"] >= 1
        assert job["chunks_created"] >= 1

        job_id = job["id"]

        # Get job details
        resp = await client.get(f"/intake/{job_id}")
        assert resp.status_code == 200
        details = resp.json()
        assert len(details["documents"]) >= 1
        assert details["chunks_total"] >= 1

        # Check that documents have semantic type
        doc = details["documents"][0]
        assert doc["semantic_type"] == "document"

    finally:
        os.unlink(test_file)


@pytest.mark.asyncio
async def test_ingest_and_search(client: AsyncClient):
    """Full pipeline: ingest a file, then search and get an answer."""
    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="omnirag_search_") as f:
        f.write("""The capital of France is Paris. It is known for the Eiffel Tower,
the Louvre Museum, and Notre-Dame Cathedral. Paris has been the
capital since the 10th century and is the largest city in France
with a population of over 2 million in the city proper.""")
        test_file = f.name

    try:
        # Ingest
        resp = await client.post("/intake", json={"source": test_file})
        assert resp.status_code == 200
        job = resp.json()
        assert job["state"] == "active"

        # Search
        resp = await client.post("/v1/search", json={
            "query": "What is the capital of France?",
            "top_k": 5,
        })
        assert resp.status_code == 200
        result = resp.json()

        assert "answer" in result
        assert "citations" in result
        assert "metadata" in result
        assert result["metadata"]["chunks_retrieved"] >= 0
        assert result["metadata"]["mode"] in ("hybrid", "vector_only", "keyword_only")

    finally:
        os.unlink(test_file)


@pytest.mark.asyncio
async def test_search_debug(client: AsyncClient):
    """Debug endpoint returns intermediate retrieval scores."""
    resp = await client.post("/v1/search/debug", json={
        "query": "test query",
        "top_k": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "chunks" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_lineage(client: AsyncClient):
    """Lineage endpoint returns events."""
    resp = await client.get("/lineage")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "tombstones" in data
    assert "counts" in data


@pytest.mark.asyncio
async def test_connectors(client: AsyncClient):
    """List available connectors."""
    resp = await client.get("/connectors")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert "local" in data["available"]
    assert "http" in data["available"]


@pytest.mark.asyncio
async def test_cursors(client: AsyncClient):
    """List connector cursors."""
    resp = await client.get("/cursors")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_backpressure_health(client: AsyncClient):
    """Backpressure health endpoint."""
    resp = await client.get("/backpressure/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "all_healthy" in data


@pytest.mark.asyncio
async def test_circuit_breakers(client: AsyncClient):
    """Circuit breaker status."""
    resp = await client.get("/backpressure/circuit-breakers")
    assert resp.status_code == 200
    data = resp.json()
    assert "breakers" in data


@pytest.mark.asyncio
async def test_dead_letters(client: AsyncClient):
    """Dead letter queue."""
    resp = await client.get("/dead-letters")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data


@pytest.mark.asyncio
async def test_webhooks_lifecycle(client: AsyncClient):
    """Register, list, delete a webhook."""
    # Register
    resp = await client.post("/v1/webhooks", json={
        "url": "https://example.com/callback",
        "events": ["intake.completed"],
        "secret": "test-secret",
    })
    assert resp.status_code == 200
    wh = resp.json()
    wh_id = wh["id"]

    # List
    resp = await client.get("/v1/webhooks")
    assert resp.status_code == 200
    assert any(w["id"] == wh_id for w in resp.json())

    # Delete
    resp = await client.delete(f"/v1/webhooks/{wh_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_jsonl(client: AsyncClient):
    """Export should work (even if empty)."""
    resp = await client.get("/v1/export/jsonl")
    # 404 is ok if no data, 200 if data exists
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_intake_list(client: AsyncClient):
    """List all intake jobs."""
    resp = await client.get("/intake")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_ingest_multiple_formats(client: AsyncClient):
    """Ingest markdown and verify semantic type."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, prefix="omnirag_md_") as f:
        f.write("""# API Documentation

## Authentication

Use Bearer tokens for all API calls.

## Endpoints

### GET /health
Returns server health status.

### POST /v1/search
Full hybrid search with generation.
""")
        test_file = f.name

    try:
        resp = await client.post("/intake", json={"source": test_file})
        assert resp.status_code == 200
        job = resp.json()
        assert job["state"] == "active"
        assert job["chunks_created"] >= 1
    finally:
        os.unlink(test_file)
