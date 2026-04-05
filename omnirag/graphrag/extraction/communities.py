"""Community detection — Leiden → Louvain → connected components fallback."""

from __future__ import annotations

from typing import Any

import structlog

from omnirag.graphrag.models import GraphCommunity, GraphRelationship

logger = structlog.get_logger(__name__)

LEIDEN_RESOLUTION = 1.0


def detect_communities(entities: list[str], relationships: list[GraphRelationship],
                       resolution: float = LEIDEN_RESOLUTION) -> list[GraphCommunity]:
    """Run community detection. Tries: Leiden → Louvain → connected components."""

    if len(entities) < 2:
        if entities:
            return [GraphCommunity(entity_ids=entities, level=0)]
        return []

    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(entities)
        for rel in relationships:
            if rel.source_id in entities and rel.target_id in entities:
                G.add_edge(rel.source_id, rel.target_id, weight=rel.weight)

        # Try 1: Leiden via cdlib
        try:
            from cdlib import algorithms
            result = algorithms.leiden(G, resolution_parameter=resolution)
            communities = [GraphCommunity(entity_ids=list(m), level=0) for m in result.communities]
            logger.info("communities.leiden", count=len(communities))
            return communities
        except ImportError:
            pass

        # Try 2: Louvain (built into networkx)
        try:
            from networkx.algorithms.community import louvain_communities
            partitions = louvain_communities(G, resolution=resolution, seed=42)
            communities = [GraphCommunity(entity_ids=list(p), level=0) for p in partitions if len(p) >= 2]
            if communities:
                logger.info("communities.louvain", count=len(communities))
                return communities
        except Exception as e:
            logger.warning("communities.louvain_failed", error=str(e))

        # Try 3: Connected components
        components = list(nx.connected_components(G))
        communities = [GraphCommunity(entity_ids=list(c), level=0) for c in components if len(c) >= 2]
        logger.info("communities.components", count=len(communities))
        return communities

    except ImportError:
        logger.warning("communities.no_networkx")
        return [GraphCommunity(entity_ids=entities, level=0)]


def propagate_acl(community: GraphCommunity, entity_acls: dict[str, list[str]]) -> None:
    """Set community ACL as union of member entity ACLs."""
    principals: set[str] = set()
    for eid in community.entity_ids:
        for p in entity_acls.get(eid, []):
            principals.add(p)
    community.acl_principals = list(principals)
