"""Community detection — Leiden algorithm with hierarchy."""

from __future__ import annotations

from typing import Any

import structlog

from omnirag.graphrag.models import GraphCommunity, GraphRelationship

logger = structlog.get_logger(__name__)

LEIDEN_RESOLUTION = 1.0


def detect_communities(entities: list[str], relationships: list[GraphRelationship],
                       resolution: float = LEIDEN_RESOLUTION) -> list[GraphCommunity]:
    """Run Leiden community detection. Falls back to connected components."""

    if len(entities) < 2:
        if entities:
            return [GraphCommunity(entity_ids=entities, level=0)]
        return []

    # Build adjacency
    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(entities)
        for rel in relationships:
            if rel.source_id in entities and rel.target_id in entities:
                G.add_edge(rel.source_id, rel.target_id, weight=rel.weight)

        # Try Leiden via cdlib
        try:
            from cdlib import algorithms
            result = algorithms.leiden(G, resolution_parameter=resolution)
            communities = []
            for i, members in enumerate(result.communities):
                communities.append(GraphCommunity(
                    entity_ids=list(members), level=0,
                ))
            logger.info("communities.leiden", count=len(communities))
            return communities
        except ImportError:
            logger.warning("communities.no_cdlib", msg="falling back to connected components")

        # Fallback: connected components
        components = list(nx.connected_components(G))
        communities = []
        for comp in components:
            if len(comp) >= 2:
                communities.append(GraphCommunity(entity_ids=list(comp), level=0))
        logger.info("communities.components", count=len(communities))
        return communities

    except ImportError:
        logger.warning("communities.no_networkx", msg="returning single community")
        return [GraphCommunity(entity_ids=entities, level=0)]


def propagate_acl(community: GraphCommunity, entity_acls: dict[str, list[str]]) -> None:
    """Set community ACL as union of member entity ACLs."""
    principals: set[str] = set()
    for eid in community.entity_ids:
        for p in entity_acls.get(eid, []):
            principals.add(p)
    community.acl_principals = list(principals)
