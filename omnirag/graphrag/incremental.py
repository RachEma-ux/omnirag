"""Incremental community updates — staleness tracking + delta recompute."""

from __future__ import annotations

import time

import structlog

from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.extraction.communities import detect_communities, propagate_acl
from omnirag.graphrag.extraction.reports import generate_community_report
from omnirag.graphrag.models import GraphCommunity, GraphEntity

logger = structlog.get_logger(__name__)

STALE_THRESHOLD = 0.2  # 20% of chunks changed → recompute


class ChunkCommunityMap:
    """Maps chunks to communities for staleness tracking."""

    def __init__(self) -> None:
        self._chunk_to_community: dict[str, str] = {}
        self._stale_communities: dict[str, float] = {}  # community_id → staleness_score

    def assign(self, chunk_id: str, community_id: str) -> None:
        self._chunk_to_community[chunk_id] = community_id

    def mark_chunk_changed(self, chunk_id: str) -> None:
        """Mark the community containing this chunk as potentially stale."""
        community_id = self._chunk_to_community.get(chunk_id)
        if not community_id:
            return
        # Count stale chunks in this community
        total = sum(1 for c in self._chunk_to_community.values() if c == community_id)
        stale = self._stale_communities.get(community_id, 0) + 1
        score = stale / max(total, 1)
        self._stale_communities[community_id] = score

    def get_stale(self, threshold: float = STALE_THRESHOLD) -> list[tuple[str, float]]:
        """Return communities with staleness > threshold."""
        return [(cid, score) for cid, score in self._stale_communities.items() if score > threshold]

    def clear_stale(self, community_id: str) -> None:
        self._stale_communities.pop(community_id, None)

    def get_chunks_for_community(self, community_id: str) -> list[str]:
        return [cid for cid, com in self._chunk_to_community.items() if com == community_id]


class IncrementalUpdateEngine:
    """Runs incremental community updates.

    - On chunk change: mark affected community stale
    - Every 5 minutes: recompute communities with staleness >20%
    - Nightly: full recompute of all communities
    """

    def __init__(self) -> None:
        self.chunk_map = ChunkCommunityMap()
        self.last_run = 0.0
        self.stats = {"incremental_runs": 0, "communities_recomputed": 0, "full_rebuilds": 0}

    def on_chunk_changed(self, chunk_id: str) -> None:
        """Called when a chunk is created, updated, or deleted."""
        self.chunk_map.mark_chunk_changed(chunk_id)

    async def run_incremental(self) -> dict:
        """Recompute stale communities."""
        store = get_graph_store()
        stale = self.chunk_map.get_stale()
        recomputed = 0

        for community_id, staleness in stale:
            community = store._communities.get(community_id)
            if not community:
                self.chunk_map.clear_stale(community_id)
                continue

            # Get relationships involving community entities
            rels = [r for r in store._relationships
                    if r.source_id in community.entity_ids or r.target_id in community.entity_ids]

            # Re-run community detection on this subgraph
            new_communities = detect_communities(community.entity_ids, rels)

            if len(new_communities) == 1:
                # No structural change — just refresh report
                entity_map = {e.resolved_id: e for e in store.get_all_entities() if e.resolved_id in community.entity_ids}
                entity_acl = {eid: e.acl_principals for eid, e in entity_map.items()}
                propagate_acl(community, entity_acl)
                await store.upsert_community(community)

                rel_summaries = [f"{entity_map.get(r.source_id, GraphEntity()).canonical_name} → "
                                 f"{entity_map.get(r.target_id, GraphEntity()).canonical_name}"
                                 for r in rels if r.source_id in entity_map and r.target_id in entity_map]
                report = await generate_community_report(
                    community, list(entity_map.values()), rel_summaries
                )
                await store.upsert_report(report)
            else:
                # Split/merge — update community hierarchy
                for new_comm in new_communities:
                    entity_acl = {eid: store._entities.get(eid, GraphEntity()).acl_principals
                                  for eid in new_comm.entity_ids}
                    propagate_acl(new_comm, entity_acl)
                    await store.upsert_community(new_comm)

            self.chunk_map.clear_stale(community_id)
            recomputed += 1

        self.stats["incremental_runs"] += 1
        self.stats["communities_recomputed"] += recomputed
        self.last_run = time.time()

        logger.info("incremental.complete", stale_found=len(stale), recomputed=recomputed)
        return {"stale_found": len(stale), "recomputed": recomputed}

    def get_stale_count(self) -> int:
        return len(self.chunk_map.get_stale())


_engine = IncrementalUpdateEngine()


def get_incremental_engine() -> IncrementalUpdateEngine:
    return _engine
