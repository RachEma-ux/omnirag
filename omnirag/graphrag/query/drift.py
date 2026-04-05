"""DRIFT search — global → extract entities → local refinement."""

from __future__ import annotations

import re
import time

import structlog

from omnirag.graphrag.query.local import local_search
from omnirag.graphrag.query.global_search import global_search
from omnirag.graphrag.models import GraphEvidenceBundle, QueryMode

logger = structlog.get_logger(__name__)

DRIFT_DECAY = 0.5
TOP_ENTITIES_FROM_GLOBAL = 3


async def drift_search(query: str, acl_principals: list[str], max_hops: int = 2) -> GraphEvidenceBundle:
    """Two-phase: global retrieval → extract top entities → local refinement → merge."""
    start = time.monotonic()

    # Phase 1: Global search
    global_result = await global_search(query, acl_principals)

    # Extract entity names from global answer
    entity_names: list[str] = []
    for chunk in global_result.chunks:
        content = chunk.get("content", "")
        # Extract capitalized multi-word proper nouns as entity candidates
        candidates = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', content)
        entity_names.extend(candidates)

    # Deduplicate and take top N
    seen: set[str] = set()
    unique_entities: list[str] = []
    for name in entity_names:
        lower = name.lower()
        if lower not in seen and len(name) > 2:
            seen.add(lower)
            unique_entities.append(name)
    unique_entities = unique_entities[:TOP_ENTITIES_FROM_GLOBAL]

    if not unique_entities:
        global_result.mode = QueryMode.DRIFT
        global_result.latency_ms = (time.monotonic() - start) * 1000
        return global_result

    # Phase 2: Local search for each entity
    all_chunks = list(global_result.chunks)
    all_entities = list(global_result.entities)
    all_relationships = list(global_result.relationships)

    for entity_name in unique_entities:
        local_result = await local_search(
            f"details about {entity_name}", acl_principals, max_hops=max_hops
        )
        # Merge with decay
        for chunk in local_result.chunks:
            chunk["drift_decay"] = DRIFT_DECAY
            all_chunks.append(chunk)
        all_entities.extend(local_result.entities)
        all_relationships.extend(local_result.relationships)

    # Compute confidence: combine global and local
    confidence = min(1.0, (global_result.confidence + sum(
        1.0 for _ in unique_entities if any(
            e.get("canonical_name", "").lower() == n.lower()
            for e in all_entities for n in unique_entities
        )
    ) / max(len(unique_entities), 1)) / 2)

    coverage = min(1.0, len(all_chunks) / 20)

    return GraphEvidenceBundle(
        mode=QueryMode.DRIFT,
        chunks=all_chunks,
        entities=all_entities,
        relationships=all_relationships,
        community_reports=global_result.community_reports,
        confidence=confidence,
        coverage=coverage,
        latency_ms=(time.monotonic() - start) * 1000,
    )
