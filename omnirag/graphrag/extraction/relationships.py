"""Relationship extraction — co-occurrence weighting."""

from __future__ import annotations

from itertools import combinations

from omnirag.graphrag.models import GraphEntity, GraphRelationship

WEIGHT_SAME_CHUNK = 1.0
WEIGHT_DECAY = 0.5
WEIGHT_CAP = 5.0


def extract_relationships(entities_by_chunk: dict[str, list[GraphEntity]],
                          chunk_order: list[str] | None = None) -> list[GraphRelationship]:
    """Extract relationships from co-occurring entities.

    - Same chunk: weight 1.0 per co-occurrence
    - Adjacent chunks: weight 0.5 (decay)
    - Cap at 5.0
    """
    rel_map: dict[tuple[str, str], GraphRelationship] = {}

    # Same-chunk co-occurrences
    for chunk_id, entities in entities_by_chunk.items():
        for e1, e2 in combinations(entities, 2):
            key = tuple(sorted([e1.resolved_id, e2.resolved_id]))
            if key not in rel_map:
                rel_map[key] = GraphRelationship(
                    source_id=key[0], target_id=key[1],
                    weight=0, chunk_ids=[], acl_principals=[],
                )
            rel = rel_map[key]
            rel.weight = min(WEIGHT_CAP, rel.weight + WEIGHT_SAME_CHUNK)
            rel.chunk_ids.append(chunk_id)
            # Union ACL
            for e in (e1, e2):
                for p in e.acl_principals:
                    if p not in rel.acl_principals:
                        rel.acl_principals.append(p)

    # Adjacent-chunk co-occurrences (sliding window of 3)
    if chunk_order:
        for i in range(len(chunk_order)):
            window = chunk_order[max(0, i - 1):i + 2]
            all_entities = []
            for cid in window:
                if cid in entities_by_chunk:
                    all_entities.extend(entities_by_chunk[cid])

            seen_pairs = set()
            for e1, e2 in combinations(all_entities, 2):
                if e1.resolved_id == e2.resolved_id:
                    continue
                key = tuple(sorted([e1.resolved_id, e2.resolved_id]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                # Only add decay weight for cross-chunk pairs
                same_chunk = any(
                    e1.resolved_id in [x.resolved_id for x in entities_by_chunk.get(cid, [])]
                    and e2.resolved_id in [x.resolved_id for x in entities_by_chunk.get(cid, [])]
                    for cid in window
                )
                if same_chunk:
                    continue  # already counted above

                if key not in rel_map:
                    rel_map[key] = GraphRelationship(
                        source_id=key[0], target_id=key[1],
                        weight=0, chunk_ids=[], acl_principals=[],
                    )
                rel_map[key].weight = min(WEIGHT_CAP, rel_map[key].weight + WEIGHT_DECAY)

    return list(rel_map.values())
