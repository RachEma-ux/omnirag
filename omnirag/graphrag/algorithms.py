"""Graph algorithms — PageRank, centrality, multi-resolution Leiden."""

from __future__ import annotations

import structlog

from omnirag.graphrag.models import GraphCommunity, GraphRelationship

logger = structlog.get_logger(__name__)


def compute_pagerank(entities: list[str], relationships: list[GraphRelationship],
                     damping: float = 0.85, iterations: int = 100) -> dict[str, float]:
    """Compute PageRank scores for entities. Used for context budget prioritization."""
    try:
        import networkx as nx
        G = nx.DiGraph()
        G.add_nodes_from(entities)
        for rel in relationships:
            if rel.source_id in entities and rel.target_id in entities:
                G.add_edge(rel.source_id, rel.target_id, weight=rel.weight)
        scores = nx.pagerank(G, alpha=damping, max_iter=iterations)
        logger.info("pagerank.computed", nodes=len(entities), edges=len(relationships))
        return scores
    except ImportError:
        logger.warning("pagerank.no_networkx")
        # Fallback: uniform scores
        score = 1.0 / max(len(entities), 1)
        return {e: score for e in entities}


def compute_betweenness_centrality(entities: list[str],
                                   relationships: list[GraphRelationship]) -> dict[str, float]:
    """Compute betweenness centrality."""
    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(entities)
        for rel in relationships:
            if rel.source_id in entities and rel.target_id in entities:
                G.add_edge(rel.source_id, rel.target_id, weight=rel.weight)
        return nx.betweenness_centrality(G)
    except ImportError:
        return {e: 0.0 for e in entities}


def multi_resolution_leiden(entities: list[str], relationships: list[GraphRelationship],
                            resolutions: list[float] | None = None) -> list[GraphCommunity]:
    """Run Leiden at multiple resolutions to build a hierarchical community structure.

    Default resolutions: γ=0.5 (broad), γ=1.0 (medium), γ=2.0 (fine)
    Returns flat list of communities with level + parent_community_id set.
    """
    if resolutions is None:
        resolutions = [0.5, 1.0, 2.0]

    all_communities: list[GraphCommunity] = []
    prev_level_communities: list[GraphCommunity] = []

    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(entities)
        for rel in relationships:
            if rel.source_id in entities and rel.target_id in entities:
                G.add_edge(rel.source_id, rel.target_id, weight=rel.weight)

        for level, resolution in enumerate(resolutions):
            try:
                from cdlib import algorithms
                result = algorithms.leiden(G, resolution_parameter=resolution)
                level_communities = []
                for members in result.communities:
                    comm = GraphCommunity(entity_ids=list(members), level=level)
                    # Find parent: which prev_level community has most overlap
                    if prev_level_communities:
                        best_parent = None
                        best_overlap = 0
                        member_set = set(members)
                        for parent in prev_level_communities:
                            overlap = len(member_set & set(parent.entity_ids))
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_parent = parent
                        if best_parent:
                            comm.metadata = {"parent_community_id": best_parent.community_id}
                    level_communities.append(comm)

                all_communities.extend(level_communities)
                prev_level_communities = level_communities
                logger.info("leiden.level", level=level, resolution=resolution, communities=len(level_communities))

            except ImportError:
                # Fallback: connected components at each level
                components = list(nx.connected_components(G))
                for comp in components:
                    if len(comp) >= max(2, int(10 / (level + 1))):
                        all_communities.append(GraphCommunity(entity_ids=list(comp), level=level))
                break

    except ImportError:
        logger.warning("leiden.no_networkx")
        if entities:
            all_communities.append(GraphCommunity(entity_ids=entities, level=0))

    logger.info("multi_resolution_leiden.complete", total_communities=len(all_communities), levels=len(resolutions))
    return all_communities
