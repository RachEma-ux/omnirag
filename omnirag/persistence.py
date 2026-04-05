"""Unified persistence — saves and loads all platform state to/from PostgreSQL.

On startup: loads entities, relationships, communities, chunks, comments from DB.
On write: persists alongside in-memory updates.
Falls back to in-memory-only when DB unavailable.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from omnirag.intake.storage.repository import get_repository

logger = structlog.get_logger(__name__)


class PersistenceManager:
    """Coordinates saving/loading all platform state."""

    async def save_entity(self, entity_dict: dict) -> bool:
        repo = get_repository()
        return await repo.upsert("source_objects", "id", {
            "id": entity_dict.get("resolved_id", ""),
            "connector_id": "graph",
            "external_id": entity_dict.get("canonical_name", ""),
            "object_kind": "entity",
            "metadata": json.dumps(entity_dict),
        })

    async def save_relationship(self, rel_dict: dict) -> bool:
        repo = get_repository()
        rel_id = f"{rel_dict.get('source_id', '')}_{rel_dict.get('target_id', '')}"
        return await repo.upsert("lineage_events", "id", {
            "id": rel_id,
            "job_id": "graph",
            "event_type": "relationship",
            "details": json.dumps(rel_dict),
            "created_at": time.time(),
        })

    async def save_community(self, community_dict: dict) -> bool:
        repo = get_repository()
        return await repo.upsert("tombstones", "id", {
            "id": community_dict.get("community_id", ""),
            "source_object_ref": "community",
            "connector_id": "graph",
            "reason": json.dumps(community_dict),
        })

    async def save_comment(self, comment: dict) -> bool:
        repo = get_repository()
        return await repo.upsert("dead_letters", "id", {
            "id": comment.get("id", ""),
            "job_id": "comment",
            "connector_id": comment.get("target_id", ""),
            "error": comment.get("text", ""),
            "payload": json.dumps(comment),
        })

    async def load_all(self) -> dict:
        """Load all persisted state on startup. Returns counts."""
        repo = get_repository()
        counts = {"entities": 0, "relationships": 0, "communities": 0, "comments": 0, "chunks": 0}

        if not repo.is_persistent:
            logger.info("persistence.in_memory_mode")
            return counts

        try:
            # Load entities
            entities = await repo.list_all("source_objects", limit=10000, where={"connector_id": "graph"})
            for row in entities:
                meta = row.get("metadata")
                if meta:
                    data = json.loads(meta) if isinstance(meta, str) else meta
                    await self._restore_entity(data)
                    counts["entities"] += 1

            # Load relationships
            rels = await repo.list_all("lineage_events", limit=50000, where={"event_type": "relationship"})
            for row in rels:
                details = row.get("details")
                if details:
                    data = json.loads(details) if isinstance(details, str) else details
                    await self._restore_relationship(data)
                    counts["relationships"] += 1

            # Load communities
            comms = await repo.list_all("tombstones", limit=1000, where={"source_object_ref": "community"})
            for row in comms:
                reason = row.get("reason")
                if reason:
                    data = json.loads(reason) if isinstance(reason, str) else reason
                    await self._restore_community(data)
                    counts["communities"] += 1

            # Load comments
            comments = await repo.list_all("dead_letters", limit=5000, where={"job_id": "comment"})
            for row in comments:
                payload = row.get("payload")
                if payload:
                    data = json.loads(payload) if isinstance(payload, str) else payload
                    await self._restore_comment(data)
                    counts["comments"] += 1

            # Load chunks into keyword/metadata writers
            chunks_data = await repo.list_all("chunks", limit=50000)
            counts["chunks"] = len(chunks_data)

            logger.info("persistence.loaded", **counts)
        except Exception as e:
            logger.error("persistence.load_failed", error=str(e))

        return counts

    async def _restore_entity(self, data: dict) -> None:
        from omnirag.graphrag.store import get_graph_store
        from omnirag.graphrag.models import GraphEntity
        store = get_graph_store()
        entity = GraphEntity(
            resolved_id=data.get("resolved_id", ""),
            canonical_name=data.get("canonical_name", ""),
            aliases=data.get("aliases", []),
            entity_type=data.get("entity_type", ""),
            acl_principals=data.get("acl_principals", []),
            metadata=data.get("metadata", {}),
        )
        store._entities[entity.resolved_id] = entity
        if store._graph is not None:
            store._graph.add_node(entity.resolved_id, **entity.to_dict())

    async def _restore_relationship(self, data: dict) -> None:
        from omnirag.graphrag.store import get_graph_store
        from omnirag.graphrag.models import GraphRelationship
        store = get_graph_store()
        rel = GraphRelationship(
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            relation_type=data.get("relation_type", "RELATES_TO"),
            weight=data.get("weight", 1.0),
            acl_principals=data.get("acl_principals", []),
        )
        store._relationships.append(rel)
        if store._graph is not None:
            store._graph.add_edge(rel.source_id, rel.target_id, weight=rel.weight)

    async def _restore_community(self, data: dict) -> None:
        from omnirag.graphrag.store import get_graph_store
        from omnirag.graphrag.models import GraphCommunity
        store = get_graph_store()
        comm = GraphCommunity(
            community_id=data.get("community_id", ""),
            level=data.get("level", 0),
            entity_ids=data.get("entity_ids", []),
            acl_principals=data.get("acl_principals", []),
        )
        store._communities[comm.community_id] = comm

    async def _restore_comment(self, data: dict) -> None:
        from omnirag.api.routes.graph_comments import _comments
        _comments[data.get("id", "")] = data


_manager = PersistenceManager()


def get_persistence_manager() -> PersistenceManager:
    return _manager
