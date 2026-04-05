"""Local search — entity-centric graph traversal + linked chunks."""

from __future__ import annotations

import time

import structlog

from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.extraction.entities import get_entity_extractor
from omnirag.graphrag.extraction.resolution import get_entity_resolver
from omnirag.graphrag.models import GraphEvidenceBundle, QueryMode

logger = structlog.get_logger(__name__)

DEFAULT_MAX_HOPS = 2


async def local_search(query: str, acl_principals: list[str],
                       max_hops: int = DEFAULT_MAX_HOPS) -> GraphEvidenceBundle:
    """Entity-centric retrieval: extract entities from query → resolve → traverse → collect chunks."""
    start = time.monotonic()
    store = get_graph_store()
    extractor = get_entity_extractor()
    resolver = get_entity_resolver()

    # 1. Extract entities from query
    mentions = extractor.extract(query, chunk_id="query")
    if not mentions:
        return GraphEvidenceBundle(mode=QueryMode.LOCAL, confidence=0.0,
                                  latency_ms=(time.monotonic() - start) * 1000)

    # 2. Resolve to entity IDs
    entity_ids = []
    for m in mentions:
        rid = resolver.lookup(m.surface_form)
        if rid:
            entity_ids.append(rid)
        else:
            # Try store lookup by name
            entity = await store.find_entity_by_name(m.surface_form)
            if entity:
                entity_ids.append(entity.resolved_id)

    if not entity_ids:
        return GraphEvidenceBundle(mode=QueryMode.LOCAL, confidence=0.0,
                                  latency_ms=(time.monotonic() - start) * 1000)

    # 3. Traverse graph for each entity
    all_entities = []
    all_relationships = []
    all_chunk_ids: set[str] = set()

    for eid in entity_ids:
        neighbors = await store.get_neighbors(eid, max_hops=max_hops, acl_principals=acl_principals)
        for n in neighbors:
            all_entities.append(n["entity"])

        # Get linked chunks
        chunks = await store.get_chunks_for_entity(eid, acl_principals=acl_principals)
        all_chunk_ids.update(chunks)

        # Add the entity itself
        entity = await store.get_entity(eid)
        if entity:
            all_entities.append(entity.to_dict())

    # 4. Build evidence bundle
    confidence = min(1.0, len(entity_ids) / max(len(mentions), 1))

    return GraphEvidenceBundle(
        mode=QueryMode.LOCAL,
        entities=all_entities,
        relationships=all_relationships,
        chunks=[{"chunk_id": cid} for cid in all_chunk_ids],
        confidence=confidence,
        coverage=min(1.0, len(all_chunk_ids) / 10),
        latency_ms=(time.monotonic() - start) * 1000,
    )
