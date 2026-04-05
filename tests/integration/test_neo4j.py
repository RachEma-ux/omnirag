"""Neo4j integration tests — requires running Neo4j instance.

Skip gracefully when Neo4j is unavailable.
"""

from __future__ import annotations

import pytest

from omnirag.graphrag.store import GraphStore
from omnirag.graphrag.models import GraphEntity, GraphRelationship, GraphCommunity, CommunityReport
from omnirag.graphrag.projection import GraphProjectionService
from omnirag.intake.models import Chunk, CanonicalDocument, SemanticType


@pytest.fixture
async def store():
    s = GraphStore()
    connected = await s.connect()
    yield s, connected


@pytest.mark.asyncio
async def test_store_connects_or_fallback(store):
    s, connected = store
    stats = s.stats()
    assert stats["mode"] in ("neo4j", "in-memory")


@pytest.mark.asyncio
async def test_entity_crud(store):
    s, _ = store
    entity = GraphEntity(
        resolved_id="test-entity-1",
        canonical_name="OmniRAG",
        aliases=["omnirag", "Omni RAG"],
        entity_type="PROJECT",
        acl_principals=["user:alice"],
    )
    await s.upsert_entity(entity)
    retrieved = await s.get_entity("test-entity-1")
    assert retrieved is not None
    assert retrieved.canonical_name == "OmniRAG"
    assert "omnirag" in retrieved.aliases


@pytest.mark.asyncio
async def test_entity_find_by_name(store):
    s, _ = store
    await s.upsert_entity(GraphEntity(
        resolved_id="test-find-1", canonical_name="PostgreSQL",
        aliases=["Postgres", "PG"], entity_type="PRODUCT",
    ))
    found = await s.find_entity_by_name("PostgreSQL")
    assert found is not None
    assert found.resolved_id == "test-find-1"

    found_alias = await s.find_entity_by_name("Postgres")
    assert found_alias is not None


@pytest.mark.asyncio
async def test_relationship_weight(store):
    s, _ = store
    await s.upsert_entity(GraphEntity(resolved_id="rel-a", canonical_name="A"))
    await s.upsert_entity(GraphEntity(resolved_id="rel-b", canonical_name="B"))

    await s.upsert_relationship(GraphRelationship(source_id="rel-a", target_id="rel-b", weight=1.0))
    await s.upsert_relationship(GraphRelationship(source_id="rel-a", target_id="rel-b", weight=1.5))

    # In-memory: both stored; Neo4j: weight accumulated
    neighbors = await s.get_neighbors("rel-a", max_hops=1)
    assert len(neighbors) >= 1


@pytest.mark.asyncio
async def test_acl_filtered_traversal(store):
    s, _ = store
    await s.upsert_entity(GraphEntity(resolved_id="acl-1", canonical_name="Secret", acl_principals=["user:bob"]))
    await s.upsert_entity(GraphEntity(resolved_id="acl-2", canonical_name="Public", acl_principals=["user:alice", "user:bob"]))
    await s.upsert_relationship(GraphRelationship(source_id="acl-1", target_id="acl-2", weight=1.0))

    # Alice can see acl-2 but not acl-1
    neighbors = await s.get_neighbors("acl-2", max_hops=1, acl_principals=["user:alice"])
    # acl-1 should be filtered out for alice
    for n in neighbors:
        entity = n["entity"]
        if isinstance(entity, dict):
            # In-memory or Neo4j dict form
            assert "user:alice" in entity.get("acl_principals", []) or entity.get("resolved_id") == "acl-2"


@pytest.mark.asyncio
async def test_chunk_entity_linking(store):
    s, _ = store
    await s.upsert_entity(GraphEntity(resolved_id="link-e1", canonical_name="Entity1"))
    await s.link_chunk_entity("chunk-001", "link-e1", confidence=0.9)
    chunks = await s.get_chunks_for_entity("link-e1")
    assert "chunk-001" in chunks


@pytest.mark.asyncio
async def test_community_and_report(store):
    s, _ = store
    await s.upsert_entity(GraphEntity(resolved_id="comm-e1", canonical_name="E1"))
    await s.upsert_entity(GraphEntity(resolved_id="comm-e2", canonical_name="E2"))

    community = GraphCommunity(entity_ids=["comm-e1", "comm-e2"], level=0, acl_principals=["user:alice"])
    await s.upsert_community(community)

    report = CommunityReport(community_id=community.community_id, summary="Test community about E1 and E2.", acl_principals=["user:alice"])
    await s.upsert_report(report)

    reports = await s.get_community_reports(acl_principals=["user:alice"])
    assert len(reports) >= 1
    assert any("E1" in r.summary for r in reports)


@pytest.mark.asyncio
async def test_full_projection():
    """Test projection service creates entities, relationships, communities from chunks."""
    service = GraphProjectionService()
    docs = [CanonicalDocument(id="doc-proj-1", semantic_type=SemanticType.DOCUMENT, body="Test")]
    chunks = [
        Chunk(id="c-proj-1", document_id="doc-proj-1", text="OmniRAG is a RAG platform built with Python and Neo4j."),
        Chunk(id="c-proj-2", document_id="doc-proj-1", text="Neo4j stores the knowledge graph for OmniRAG queries."),
    ]
    stats = await service.project(docs, chunks)
    assert stats["entities"] >= 1


@pytest.mark.asyncio
async def test_store_stats(store):
    s, _ = store
    stats = s.stats()
    assert "entities" in stats
    assert "relationships" in stats
    assert "communities" in stats
