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

    def resolve(self, mentions: list[EntityMention]) -> list[GraphEntity]:
        """Cluster mentions into canonical entities."""
        if not mentions:
            return []

        # Try HDBSCAN clustering
        embedder = self._get_embedder()
        if embedder and len(mentions) >= 2:
            return self._resolve_with_clustering(mentions, embedder)

        # Fallback: exact string matching
        return self._resolve_exact(mentions)

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
