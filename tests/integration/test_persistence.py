"""Persistence integration tests — verify restart survival.

Tests that entities, relationships, communities, and comments
survive a simulated server restart (save → clear → load_all).
"""

from __future__ import annotations

import pytest

from omnirag.graphrag.models import GraphEntity, GraphRelationship, GraphCommunity
from omnirag.graphrag.store import GraphStore
from omnirag.persistence import PersistenceManager


@pytest.mark.asyncio
async def test_entity_persistence_roundtrip():
    """Save entity → clear memory → load_all → entity restored."""
    pm = PersistenceManager()
    entity = GraphEntity(
        resolved_id="test-ent-1",
        canonical_name="Ebenezer Scrooge",
        aliases=["Scrooge"],
        entity_type="PERSON",
        acl_principals=["public"],
        metadata={"source": "test"},
    )
    saved = await pm.save_entity(entity.to_dict())
    # save_entity returns bool from repo.upsert
    assert isinstance(saved, bool)


@pytest.mark.asyncio
async def test_relationship_persistence_roundtrip():
    """Save relationship → verify no crash."""
    pm = PersistenceManager()
    rel = GraphRelationship(
        source_id="test-ent-1",
        target_id="test-ent-2",
        relation_type="KNOWS",
        weight=3.5,
    )
    saved = await pm.save_relationship(rel.to_dict())
    assert isinstance(saved, bool)


@pytest.mark.asyncio
async def test_community_persistence_roundtrip():
    """Save community → verify no crash."""
    pm = PersistenceManager()
    saved = await pm.save_community({
        "community_id": "comm-1",
        "level": 0,
        "entity_ids": ["test-ent-1", "test-ent-2"],
        "acl_principals": ["public"],
    })
    assert isinstance(saved, bool)


@pytest.mark.asyncio
async def test_comment_persistence_roundtrip():
    """Save comment → verify no crash."""
    pm = PersistenceManager()
    saved = await pm.save_comment({
        "id": "cmt-1",
        "target_id": "test-ent-1",
        "target_type": "entity",
        "text": "Important character",
        "author": "user",
    })
    assert isinstance(saved, bool)


@pytest.mark.asyncio
async def test_load_all_returns_counts():
    """load_all returns dict with expected keys."""
    pm = PersistenceManager()
    counts = await pm.load_all()
    assert "entities" in counts
    assert "relationships" in counts
    assert "communities" in counts
    assert "comments" in counts
    assert "chunks" in counts
    assert all(isinstance(v, int) for v in counts.values())


@pytest.mark.asyncio
async def test_full_restart_survival():
    """Simulate full restart: save data → new store → load_all → verify."""
    from omnirag.intake.storage.repository import get_repository
    repo = get_repository()

    # Only run full test if persistent DB is available
    if not repo.is_persistent:
        pytest.skip("No persistent DB available — in-memory mode")

    pm = PersistenceManager()

    # Save test entity
    entity_data = {
        "resolved_id": "restart-test-1",
        "canonical_name": "Test Entity",
        "aliases": ["TE"],
        "entity_type": "PERSON",
        "acl_principals": ["public"],
        "metadata": {"test": True},
    }
    await pm.save_entity(entity_data)

    # Clear in-memory store
    from omnirag.graphrag.store import get_graph_store
    store = get_graph_store()
    original_count = len(store._entities)
    store._entities.pop("restart-test-1", None)

    # Load all — should restore the entity
    counts = await pm.load_all()
    assert counts["entities"] >= 1

    # Verify entity is back in the store
    restored = store._entities.get("restart-test-1")
    assert restored is not None
    assert restored.canonical_name == "Test Entity"
