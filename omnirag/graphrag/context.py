"""Context Builder — assembles retrieval results into ContextBundle with token budget.

Process:
1. Expand from anchor entities (N-hop)
2. Verbalize each relation: "{source} {type} {target}: {description}"
3. Attach top-k chunks (by relevance score)
4. Add community summaries (for Global mode)
5. Apply token budget: greedy by importance (PageRank + recency)
6. Deduplicate overlapping content
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from omnirag.models.canonical import ContextBundle
from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.algorithms import compute_pagerank

logger = structlog.get_logger(__name__)

DEFAULT_BUDGET = 2048
CHUNK_SCORE_THRESHOLD = 0.3


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


class GraphContextBuilder:
    """Builds context from graph traversal + chunks + communities."""

    async def build(self, anchor_entity_ids: list[str], chunks: list[dict],
                    community_summaries: list[dict] | None = None,
                    acl_principals: list[str] | None = None,
                    budget: int = DEFAULT_BUDGET,
                    max_hops: int = 2) -> ContextBundle:
        """Assemble ContextBundle with token budget enforcement."""
        start = time.monotonic()
        store = get_graph_store()
        bundle = ContextBundle(token_budget_total=budget)
        used = 0

        # 1. Expand from anchor entities (N-hop)
        expanded_entities = []
        expanded_relations = []
        for eid in anchor_entity_ids:
            entity = await store.get_entity(eid)
            if entity:
                expanded_entities.append({"id": eid, "name": entity.canonical_name,
                                          "type": entity.entity_type, "description": entity.metadata.get("description", "")})
            neighbors = await store.get_neighbors(eid, max_hops=max_hops, acl_principals=acl_principals)
            for n in neighbors:
                ent = n.get("entity", {})
                if isinstance(ent, dict):
                    expanded_entities.append(ent)

        # Deduplicate entities
        seen_entities: set[str] = set()
        unique_entities = []
        for e in expanded_entities:
            eid = e.get("resolved_id") or e.get("id", "")
            if eid and eid not in seen_entities:
                seen_entities.add(eid)
                unique_entities.append(e)
        bundle.anchor_entities = unique_entities

        # 2. Verbalize relations
        for e in unique_entities:
            eid = e.get("resolved_id") or e.get("id", "")
            if not eid:
                continue
            for rel in store._relationships:
                if rel.source_id == eid or rel.target_id == eid:
                    src_name = self._entity_name(rel.source_id, unique_entities)
                    tgt_name = self._entity_name(rel.target_id, unique_entities)
                    verbalized = f"{src_name} {rel.relation_type} {tgt_name}"
                    desc = getattr(rel, "metadata", {}).get("description", "")
                    if desc:
                        verbalized += f": {desc}"

                    tokens = estimate_tokens(verbalized)
                    if used + tokens <= budget:
                        bundle.selected_relations.append({
                            "source": src_name, "type": rel.relation_type,
                            "target": tgt_name, "description": desc,
                            "verbalized": verbalized,
                        })
                        used += tokens

        # 3. Attach chunks sorted by score
        sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0), reverse=True)
        for chunk in sorted_chunks:
            text = chunk.get("content") or chunk.get("text", "")
            score = chunk.get("score", 0)
            if score < CHUNK_SCORE_THRESHOLD and bundle.supporting_chunks:
                break
            tokens = estimate_tokens(text)
            if used + tokens > budget:
                # Truncate to fit
                remaining = (budget - used) * 4
                if remaining > 100:
                    text = text[:remaining]
                    tokens = estimate_tokens(text)
                else:
                    break
            bundle.supporting_chunks.append({"text": text, "score": score, "chunk_id": chunk.get("chunk_id", "")})
            used += tokens

        # 4. Community summaries (for Global mode)
        if community_summaries:
            for cs in community_summaries:
                summary = cs.get("summary", "")
                tokens = estimate_tokens(summary)
                if used + tokens <= budget:
                    bundle.community_summaries.append(cs)
                    used += tokens

        bundle.token_budget_used = used
        bundle.freshness_seconds = time.monotonic() - start

        logger.info("context_builder.complete",
                     entities=len(bundle.anchor_entities),
                     relations=len(bundle.selected_relations),
                     chunks=len(bundle.supporting_chunks),
                     communities=len(bundle.community_summaries),
                     tokens_used=used, budget=budget)
        return bundle

    @staticmethod
    def _entity_name(entity_id: str, entities: list[dict]) -> str:
        for e in entities:
            if (e.get("resolved_id") or e.get("id", "")) == entity_id:
                return e.get("canonical_name") or e.get("name", entity_id[:8])
        return entity_id[:8]


_builder = GraphContextBuilder()


def get_context_builder() -> GraphContextBuilder:
    return _builder
