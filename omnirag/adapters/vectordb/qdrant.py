"""Qdrant vector database adapter.

Supports both in-memory and gRPC/HTTP connections.
Requires: pip install omnirag[qdrant]
"""

from __future__ import annotations

from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import OmniChunk, RetrievalResult


@maturity_level("core")
class QdrantAdapter(BaseAdapter):
    """Qdrant vector database adapter — CRUD and search on OmniChunks."""

    def __init__(self) -> None:
        self._client: Any = None
        self._embedding_size: int | None = None

    @property
    def name(self) -> str:
        return "qdrant"

    @property
    def category(self) -> str:
        return "retrieval"

    def _get_client(self, **kwargs: Any) -> Any:
        """Lazy-init Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as e:
                raise ImportError(
                    "qdrant-client is required. "
                    "Install with: pip install omnirag[qdrant]"
                ) from e

            url: str | None = kwargs.get("url")
            if url:
                self._client = QdrantClient(url=url)
            else:
                self._client = QdrantClient(location=":memory:")
        return self._client

    def _ensure_collection(self, collection: str, vector_size: int, **kwargs: Any) -> None:
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client(**kwargs)
        collections = [c.name for c in client.get_collections().collections]
        if collection not in collections:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def store(self, chunks: list[OmniChunk], **kwargs: Any) -> None:
        """Store chunks in Qdrant.

        Params:
            collection: Collection name (required).
            url: Qdrant server URL (default: in-memory).
        """
        from qdrant_client.models import PointStruct

        collection: str = kwargs.get("collection", "default")
        client = self._get_client(**kwargs)

        # Determine embedding size from first chunk
        embedded = [c for c in chunks if c.embedding is not None]
        if not embedded:
            return

        vector_size = len(embedded[0].embedding)  # type: ignore[arg-type]
        self._ensure_collection(collection, vector_size, **kwargs)

        points = [
            PointStruct(
                id=hash(c.id) % (2**63),
                vector=c.embedding,  # type: ignore[arg-type]
                payload={
                    "chunk_id": c.id,
                    "content": c.content,
                    "modality": c.modality.value,
                    "metadata": c.metadata,
                },
            )
            for c in embedded
        ]

        client.upsert(collection_name=collection, points=points)

    def retrieve(self, query: str, **kwargs: Any) -> RetrievalResult:
        """Retrieve chunks by vector similarity.

        Params:
            query_embedding: Query vector (required).
            collection: Collection name (default: 'default').
            top_k: Number of results (default: 5).
        """
        query_embedding: list[float] | None = kwargs.get("query_embedding")
        collection: str = kwargs.get("collection", "default")
        top_k: int = kwargs.get("top_k", 5)

        if query_embedding is None:
            return RetrievalResult(
                query=query,
                provenance={"adapter": self.name, "error": "no query_embedding provided"},
            )

        client = self._get_client(**kwargs)

        results = client.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=top_k,
        )

        chunks = []
        scores = []
        for hit in results:
            payload = hit.payload or {}
            chunks.append(
                OmniChunk(
                    id=payload.get("chunk_id", str(hit.id)),
                    content=payload.get("content", ""),
                    modality=payload.get("modality", "text"),
                    metadata=payload.get("metadata", {}),
                )
            )
            scores.append(hit.score)

        return RetrievalResult(
            query=query,
            chunks=chunks,
            scores=scores,
            provenance={"adapter": self.name, "collection": collection},
        )
