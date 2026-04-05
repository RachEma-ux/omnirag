"""Entity resolution — embed → HDBSCAN → canonical name → Redis alias map."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

import structlog

from omnirag.graphrag.models import EntityMention, GraphEntity

logger = structlog.get_logger(__name__)


class EntityResolver:
    """Resolves entity mentions to canonical entities via clustering."""

    def __init__(self) -> None:
        self._alias_map: dict[str, str] = {}  # surface_form_lower → resolved_id
        self._embedder: Any = None

    def _get_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            return self._embedder
        except ImportError:
            return None

    def resolve(self, mentions: list[EntityMention]) -> tuple[list[GraphEntity], list]:
        """Resolve mentions into canonical entities with blocking + clustering + LLM verification.

        Returns: (entities, resolution_cases)
        """
        from omnirag.models.canonical import ResolutionCase

        if not mentions:
            return [], []

        resolution_cases: list[ResolutionCase] = []

        # Step 1: Blocking — group exact matches and normalized names
        blocked = self._blocking(mentions)

        # Step 2: Clustering (HDBSCAN on embeddings for non-exact groups)
        embedder = self._get_embedder()
        remaining = [m for group in blocked.values() if len(group) == 1 for m in group]
        clustered_entities = []

        if embedder and len(remaining) >= 2:
            clustered_entities = self._resolve_with_clustering(remaining, embedder)
        elif remaining:
            clustered_entities = self._resolve_exact(remaining)

        # Step 3: Convert blocked groups to entities
        blocked_entities = []
        for key, group in blocked.items():
            if len(group) >= 2:
                entity = self._cluster_to_entity(group)
                blocked_entities.append(entity)
                resolution_cases.append(ResolutionCase(
                    candidate_entity_ids=[m.surface_form for m in group],
                    merge_decision="merge",
                    confidence=0.95,
                    verification_method="exact_match",
                ))
                for m in group:
                    self._alias_map[m.surface_form.lower()] = entity.resolved_id

        all_entities = blocked_entities + clustered_entities

        # Step 4: LLM verification for borderline clusters
        all_entities, llm_cases = self._llm_verify_borderline(all_entities)
        resolution_cases.extend(llm_cases)

        return all_entities, resolution_cases

    def _blocking(self, mentions: list[EntityMention]) -> dict[str, list[EntityMention]]:
        """Group mentions by normalized name (exact match blocking)."""
        groups: dict[str, list[EntityMention]] = {}
        for m in mentions:
            key = m.surface_form.lower().strip().replace(".", "").replace(",", "")
            groups.setdefault(key, []).append(m)
        return groups

    def _llm_verify_borderline(self, entities: list[GraphEntity]) -> tuple[list[GraphEntity], list]:
        """LLM verification for entities with similar names but low clustering confidence."""
        from omnirag.models.canonical import ResolutionCase

        cases = []
        try:
            from omnirag.output.generation.engine import get_generation_engine
            from omnirag.graphrag.extraction.prompts import ENTITY_VERIFICATION_PROMPT
            import asyncio

            engine = get_generation_engine()
            if engine.get_adapter_name() == "fallback":
                return entities, cases

            # Find potentially similar pairs
            to_verify = []
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    name_sim = self._name_similarity(e1.canonical_name, e2.canonical_name)
                    if 0.4 < name_sim < 0.85:  # borderline
                        to_verify.append((e1, e2, name_sim))

            if not to_verify:
                return entities, cases

            merged_ids: set[str] = set()
            loop = asyncio.new_event_loop()
            try:
                for e1, e2, sim in to_verify[:10]:  # limit to 10 verifications
                    prompt = ENTITY_VERIFICATION_PROMPT.format(
                        entity_a_name=e1.canonical_name, entity_a_type=e1.entity_type,
                        entity_a_context=", ".join(e1.aliases[:3]),
                        entity_b_name=e2.canonical_name, entity_b_type=e2.entity_type,
                        entity_b_context=", ".join(e2.aliases[:3]),
                    )
                    result = loop.run_until_complete(engine.generate(prompt, []))
                    answer = result.answer.strip().upper()

                    if "SAME" in answer:
                        # Merge e2 into e1
                        e1.aliases.extend([e2.canonical_name] + e2.aliases)
                        e1.chunk_ids.extend(e2.chunk_ids)
                        merged_ids.add(e2.resolved_id)
                        self._alias_map[e2.canonical_name.lower()] = e1.resolved_id
                        cases.append(ResolutionCase(
                            candidate_entity_ids=[e1.resolved_id, e2.resolved_id],
                            merge_decision="merge", confidence=0.8,
                            verification_method="llm",
                            verification_trace=result.answer[:200],
                        ))
                    else:
                        cases.append(ResolutionCase(
                            candidate_entity_ids=[e1.resolved_id, e2.resolved_id],
                            merge_decision="keep_separate", confidence=0.7,
                            verification_method="llm",
                            verification_trace=result.answer[:200],
                        ))
            finally:
                loop.close()

            entities = [e for e in entities if e.resolved_id not in merged_ids]
        except Exception as e:
            logger.warning("resolution.llm_verify_failed", error=str(e))

        return entities, cases

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Simple character overlap ratio."""
        a_lower, b_lower = a.lower(), b.lower()
        if a_lower == b_lower:
            return 1.0
        shorter = min(len(a_lower), len(b_lower))
        if shorter == 0:
            return 0.0
        common = sum(1 for c in a_lower if c in b_lower)
        return common / max(len(a_lower), len(b_lower))

    def _resolve_with_clustering(self, mentions: list[EntityMention], embedder: Any) -> list[GraphEntity]:
        texts = [f"{m.surface_form} | {m.entity_type}" for m in mentions]
        embeddings = embedder.encode(texts, normalize_embeddings=True)

        try:
            import hdbscan
            import numpy as np
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=2, min_samples=1,
                metric="cosine", cluster_selection_epsilon=0.15,
            )
            labels = clusterer.fit_predict(np.array(embeddings))
        except ImportError:
            logger.warning("resolution.no_hdbscan", msg="falling back to exact matching")
            return self._resolve_exact(mentions)

        # Group by cluster
        clusters: dict[int, list[EntityMention]] = {}
        for mention, label in zip(mentions, labels):
            if label == -1:
                # Noise — treat as its own cluster
                label = -(hash(mention.surface_form.lower()) % 100000)
            clusters.setdefault(label, []).append(mention)

        entities = []
        for cluster_mentions in clusters.values():
            entity = self._cluster_to_entity(cluster_mentions)
            entities.append(entity)
            # Update alias map
            for m in cluster_mentions:
                self._alias_map[m.surface_form.lower()] = entity.resolved_id

        return entities

    def _resolve_exact(self, mentions: list[EntityMention]) -> list[GraphEntity]:
        """Simple resolution: group by lowercased surface form."""
        groups: dict[str, list[EntityMention]] = {}
        for m in mentions:
            key = m.surface_form.lower().strip()
            groups.setdefault(key, []).append(m)

        entities = []
        for group_mentions in groups.values():
            entity = self._cluster_to_entity(group_mentions)
            entities.append(entity)
            for m in group_mentions:
                self._alias_map[m.surface_form.lower()] = entity.resolved_id

        return entities

    def _cluster_to_entity(self, mentions: list[EntityMention]) -> GraphEntity:
        """Convert a cluster of mentions to a canonical entity."""
        # Most frequent surface form becomes canonical name
        counter = Counter(m.surface_form for m in mentions)
        canonical = counter.most_common(1)[0][0]
        aliases = list(set(m.surface_form for m in mentions if m.surface_form != canonical))

        # Most common entity type
        type_counter = Counter(m.entity_type for m in mentions)
        entity_type = type_counter.most_common(1)[0][0]

        # Generate stable ID from canonical name
        resolved_id = hashlib.sha256(canonical.lower().encode()).hexdigest()[:16]

        return GraphEntity(
            resolved_id=resolved_id,
            canonical_name=canonical,
            aliases=aliases,
            entity_type=entity_type,
            chunk_ids=list(set(m.chunk_id for m in mentions)),
        )

    def lookup(self, surface_form: str) -> str | None:
        """Fast lookup: surface form → resolved_id via alias map."""
        return self._alias_map.get(surface_form.lower())

    def get_alias_map(self) -> dict[str, str]:
        return dict(self._alias_map)


_resolver = EntityResolver()


def get_entity_resolver() -> EntityResolver:
    return _resolver
