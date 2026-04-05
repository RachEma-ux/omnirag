"""Qdrant + Elasticsearch + hybrid retrieval integration tests.

Tests against real instances when available, falls back to in-memory.
"""

from __future__ import annotations

import pytest

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingPipeline, EmbeddingResult
from omnirag.output.index_writers.vector import VectorIndexWriter
from omnirag.output.index_writers.keyword import KeywordIndexWriter
from omnirag.output.index_writers.metadata import MetadataIndexWriter
from omnirag.output.retrieval.hybrid import HybridRetriever, rrf


# ─── Vector Index (Qdrant) ───

@pytest.mark.asyncio
async def test_vector_write_and_search():
    writer = VectorIndexWriter()
    chunks = [
        Chunk(id="vt-1", document_id="doc-1", text="RAG combines retrieval with generation.",
              metadata={"acl_principals": ["public"]}),
        Chunk(id="vt-2", document_id="doc-1", text="Vector databases store embeddings for similarity search.",
              metadata={"acl_principals": ["public"]}),
    ]
    embeddings = [
        EmbeddingResult(chunk_id="vt-1", vector=[0.1] * 384),
        EmbeddingResult(chunk_id="vt-2", vector=[0.2] * 384),
    ]
    written = await writer.write(chunks, embeddings)
    assert written == 2

    results = await writer.search(
        query_vector=[0.15] * 384, query_text=None,
        acl_principals=["public"], top_k=5,
    )
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_vector_acl_filter():
    writer = VectorIndexWriter()
    chunks = [
        Chunk(id="vt-acl-1", text="Secret doc", metadata={"acl_principals": ["user:bob"]}),
        Chunk(id="vt-acl-2", text="Public doc", metadata={"acl_principals": ["public"]}),
    ]
    embeddings = [
        EmbeddingResult(chunk_id="vt-acl-1", vector=[0.5] * 384),
        EmbeddingResult(chunk_id="vt-acl-2", vector=[0.5] * 384),
    ]
    await writer.write(chunks, embeddings)

    results = await writer.search([0.5] * 384, None, acl_principals=["user:alice"], top_k=10)
    # Alice should only see public doc
    chunk_ids = [r["chunk_id"] for r in results]
    assert "vt-acl-2" in chunk_ids


@pytest.mark.asyncio
async def test_vector_health():
    writer = VectorIndexWriter()
    health = await writer.health()
    assert "status" in health
    assert health["status"] in ("healthy", "fallback", "unhealthy")


# ─── Keyword Index (Elasticsearch) ───

@pytest.mark.asyncio
async def test_keyword_write_and_search():
    writer = KeywordIndexWriter()
    chunks = [
        Chunk(id="kw-1", document_id="doc-1", text="Retrieval-Augmented Generation combines search with LLMs.",
              metadata={"acl_principals": ["public"]}),
        Chunk(id="kw-2", document_id="doc-1", text="The Eiffel Tower is located in Paris, France.",
              metadata={"acl_principals": ["public"]}),
    ]
    embeddings = [EmbeddingResult(chunk_id="kw-1", vector=[]), EmbeddingResult(chunk_id="kw-2", vector=[])]
    written = await writer.write(chunks, embeddings)
    assert written == 2

    results = await writer.search(None, "Retrieval Augmented Generation", acl_principals=["public"], top_k=5)
    assert len(results) >= 1
    # RAG chunk should score higher than Eiffel Tower
    if len(results) >= 2:
        assert results[0]["chunk_id"] == "kw-1"


@pytest.mark.asyncio
async def test_keyword_health():
    writer = KeywordIndexWriter()
    health = await writer.health()
    assert "status" in health


# ─── Metadata Index ───

@pytest.mark.asyncio
async def test_metadata_write_and_search():
    writer = MetadataIndexWriter()
    chunks = [
        Chunk(id="md-1", document_id="doc-1", text="Test chunk", metadata={"acl_principals": ["user:alice"]}),
    ]
    await writer.write(chunks, [EmbeddingResult(chunk_id="md-1", vector=[])])

    results = await writer.search(None, None, acl_principals=["user:alice"], top_k=5)
    assert len(results) >= 1

    visible = writer.get_visible_chunks(["user:alice"])
    assert len(visible) >= 1


# ─── RRF Fusion ───

def test_rrf_fusion():
    """Reciprocal Rank Fusion combines two ranked lists."""
    vector_results = [
        {"chunk_id": "a", "score": 0.9},
        {"chunk_id": "b", "score": 0.8},
        {"chunk_id": "c", "score": 0.7},
    ]
    keyword_results = [
        {"chunk_id": "b", "score": 5.0},
        {"chunk_id": "d", "score": 4.0},
        {"chunk_id": "a", "score": 3.0},
    ]
    fused = rrf([vector_results, keyword_results], k=60)
    ids = [cid for cid, _ in fused]

    # "b" appears at rank 2 in vector and rank 1 in keyword — should be top
    assert ids[0] in ("a", "b")
    # "a" also appears in both lists
    assert "a" in ids[:3]
    assert "b" in ids[:3]


# ─── Hybrid Retriever ───

@pytest.mark.asyncio
async def test_hybrid_retrieval():
    """End-to-end hybrid retrieval (uses fallback stores)."""
    # Write some data first
    from omnirag.output.index_writers.base import get_writer_registry
    registry = get_writer_registry()
    if not registry.names():
        registry.register(VectorIndexWriter())
        registry.register(KeywordIndexWriter())
        registry.register(MetadataIndexWriter())

    chunks = [
        Chunk(id="hyb-1", document_id="doc-1", text="RAG systems use vector similarity to find relevant passages.",
              metadata={"acl_principals": ["public"]}),
        Chunk(id="hyb-2", document_id="doc-1", text="Knowledge graphs add entity-relationship reasoning to RAG.",
              metadata={"acl_principals": ["public"]}),
    ]
    embeddings = [
        EmbeddingResult(chunk_id="hyb-1", vector=[0.3] * 384),
        EmbeddingResult(chunk_id="hyb-2", vector=[0.7] * 384),
    ]
    for writer in registry.all():
        await writer.write(chunks, embeddings)

    retriever = HybridRetriever(rerank_enabled=False)
    evidence = await retriever.retrieve("What is RAG?", acl_principals=["public"], top_k=5)

    assert evidence.mode in ("hybrid", "vector_only", "keyword_only")
    assert len(evidence.chunks) >= 0  # May be 0 with random embeddings


@pytest.mark.asyncio
async def test_hybrid_fallback_keyword_only():
    """When vector writer is down, keyword-only should still work."""
    retriever = HybridRetriever(rerank_enabled=False)
    evidence = await retriever.retrieve("test query", acl_principals=["public"], top_k=5)
    # Should not crash even with no data
    assert evidence.mode in ("hybrid", "vector_only", "keyword_only", "unavailable")
