"""In-memory vector store adapter.

Simple cosine-similarity vector store for testing and development.
No external dependencies required.
"""

from __future__ import annotations

import math
from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import OmniChunk, RetrievalResult


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@maturity_level("core")
class MemoryVectorAdapter(BaseAdapter):
    """In-memory vector store using cosine similarity."""

    def __init__(self) -> None:
        self._store: dict[str, OmniChunk] = {}

    @property
    def name(self) -> str:
        return "memory"

    @property
    def category(self) -> str:
        return "retrieval"

    def store(self, chunks: list[OmniChunk], **kwargs: Any) -> None:
        """Store chunks in memory."""
        for chunk in chunks:
            self._store[chunk.id] = chunk

    def retrieve(self, query: str, **kwargs: Any) -> RetrievalResult:
        """Retrieve chunks by cosine similarity.

        Requires a `query_embedding` kwarg (list[float]).
        """
        query_embedding: list[float] | None = kwargs.get("query_embedding")
        top_k: int = kwargs.get("top_k", 5)

        if query_embedding is None:
            return RetrievalResult(
                query=query,
                chunks=list(self._store.values())[:top_k],
                scores=[1.0] * min(top_k, len(self._store)),
                provenance={"adapter": self.name, "method": "no_embedding"},
            )

        scored: list[tuple[float, OmniChunk]] = []
        for chunk in self._store.values():
            if chunk.embedding is not None:
                score = _cosine_similarity(query_embedding, chunk.embedding)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        return RetrievalResult(
            query=query,
            chunks=[c for _, c in top],
            scores=[s for s, _ in top],
            provenance={"adapter": self.name, "method": "cosine_similarity"},
        )

    def clear(self) -> None:
        """Clear all stored chunks."""
        self._store.clear()
