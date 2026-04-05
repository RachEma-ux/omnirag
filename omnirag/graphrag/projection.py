"""Graph Projection Service — orchestrates entity/relationship/community extraction."""

from __future__ import annotations

import structlog

from omnirag.intake.models import Chunk, CanonicalDocument
from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.extraction.entities import get_entity_extractor
from omnirag.graphrag.extraction.resolution import get_entity_resolver
from omnirag.graphrag.extraction.relationships import extract_relationships
from omnirag.graphrag.extraction.communities import detect_communities, propagate_acl
from omnirag.graphrag.extraction.reports import generate_community_report
from omnirag.graphrag.models import GraphEntity

logger = structlog.get_logger(__name__)


class GraphProjectionService:
    """Orchestrates: chunks → entities → resolution → relationships → communities → reports → Neo4j."""

    async def project(self, documents: list[CanonicalDocument], chunks: list[Chunk]) -> dict:
        """Run full graph projection pipeline."""
        store = get_graph_store()
        extractor = get_entity_extractor()
        resolver = get_entity_resolver()

        stats = {"entities": 0, "relationships": 0, "communities": 0, "reports": 0}

        # 1. Extract entity mentions from all chunks
        all_mentions = []
        for chunk in chunks:
            mentions = extractor.extract(chunk.text, chunk.id)
            all_mentions.extend(mentions)

        if not all_mentions:
            logger.info("projection.no_entities")
            return stats

        # 2. Resolve mentions to canonical entities
        result = resolver.resolve(all_mentions)
        # Handle both old (list) and new (tuple) return format
        if isinstance(result, tuple):
            entities, resolution_cases = result
        else:
            entities = result
        stats["entities"] = len(entities)

        # Set ACL from document/chunk ACLs
        chunk_acl: dict[str, list[str]] = {}
        for chunk in chunks:
            chunk_acl[chunk.id] = chunk.metadata.get("acl_principals", [])

        for entity in entities:
            acl_set: set[str] = set()
            for cid in entity.chunk_ids:
                for p in chunk_acl.get(cid, []):
                    acl_set.add(p)
            entity.acl_principals = list(acl_set)

        # 3. Write entities to graph store
        for entity in entities:
            await store.upsert_entity(entity)

        # 4. Link chunks to entities
        for mention in all_mentions:
            resolved_id = resolver.lookup(mention.surface_form)
            if resolved_id:
                await store.link_chunk_entity(mention.chunk_id, resolved_id, mention.confidence)

        # 5. Extract relationships
        entities_by_chunk: dict[str, list[GraphEntity]] = {}
        for entity in entities:
            for cid in entity.chunk_ids:
                entities_by_chunk.setdefault(cid, []).append(entity)

        chunk_order = [c.id for c in chunks]
        relationships = extract_relationships(entities_by_chunk, chunk_order)
        stats["relationships"] = len(relationships)

        for rel in relationships:
            await store.upsert_relationship(rel)

        # 6. Detect communities
        entity_ids = [e.resolved_id for e in entities]
        communities = detect_communities(entity_ids, relationships)
        stats["communities"] = len(communities)

        entity_acl_map = {e.resolved_id: e.acl_principals for e in entities}
        entity_map = {e.resolved_id: e for e in entities}

        for community in communities:
            propagate_acl(community, entity_acl_map)
            await store.upsert_community(community)
            # Tag each entity with its community ID
            for eid in community.entity_ids:
                entity = store._entities.get(eid)
                if entity:
                    entity.metadata["community"] = community.community_id

        # 7. Generate community reports
        for community in communities:
            comm_entities = [entity_map[eid] for eid in community.entity_ids if eid in entity_map]
            rel_summaries = [
                f"{entity_map.get(r.source_id, GraphEntity()).canonical_name} → "
                f"{entity_map.get(r.target_id, GraphEntity()).canonical_name} (weight {r.weight:.1f})"
                for r in relationships
                if r.source_id in community.entity_ids and r.target_id in community.entity_ids
            ]
            report = await generate_community_report(community, comm_entities, rel_summaries)
            await store.upsert_report(report)
            stats["reports"] += 1

        logger.info("projection.complete", **stats)
        return stats


_service = GraphProjectionService()


def get_projection_service() -> GraphProjectionService:
    return _service
