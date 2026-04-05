"""Vector index writer — Qdrant (with in-memory fallback)."""

from __future__ import annotations

import time
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)

COLLECTION = "chunk_embeddings"
VECTOR_DIM = 384


class VectorIndexWriter(BaseIndexWriter):
    """Writes to Qdrant vector DB. Falls back to in-memory store."""

    name = "vector"

    def __init__(self) -> None:
        self._client: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = False
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import os
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            from omnirag.config.ports import QDRANT_HOST as _QH, QDRANT_PORT as _QP
            host = os.environ.get("QDRANT_HOST", _QH)
            port = int(os.environ.get("QDRANT_PORT", str(_QP)))
            self._client = QdrantClient(host=host, port=port, timeout=10)
            # Ensure collection exists
            collections = [c.name for c in self._client.get_collections().collections]
            if COLLECTION not in collections:
                self._client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
                )
            return self._client
        except Exception as e:
            logger.warning("vector.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_map = {e.chunk_id: e.vector for e in embeddings if e.status == "completed" and e.vector}
        written = 0

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    from qdrant_client.models import PointStruct
                    points = []
                    for chunk in chunks:
                        vec = embed_map.get(chunk.id)
                        if not vec:
                            continue
                        points.append(PointStruct(
                            id=chunk.id,
                            vector=vec,
                            payload={
                                "chunk_id": chunk.id,
                                "doc_id": chunk.document_id,
                                "acl_principals": chunk.metadata.get("acl_principals", []),
                                "text": chunk.text[:500],
                                "chunk_type": chunk.chunk_type,
                                "order": chunk.order,
                            },
                        ))
                    if points:
                        client.upsert(collection_name=COLLECTION, points=points)
                        written = len(points)
                        self.stats["written"] += written
                    return written
                except Exception as e:
                    logger.error("vector.write_error", error=str(e))
                    self.stats["errors"] += 1
                    self._use_fallback = True

        # In-memory fallback
        for chunk in chunks:
            vec = embed_map.get(chunk.id)
            if not vec:
                continue
            self._fallback[chunk.id] = {
                "vector": vec,
                "chunk_id": chunk.id,
                "doc_id": chunk.document_id,
                "text": chunk.text,
                "acl_principals": chunk.metadata.get("acl_principals", []),
                "metadata": chunk.metadata,
            }
            written += 1
        self.stats["written"] += written
        return written

    async def delete(self, chunk_ids: list[str]) -> int:
        deleted = 0
        for cid in chunk_ids:
            if cid in self._fallback:
                del self._fallback[cid]
                deleted += 1
        self.stats["deleted"] += deleted
        return deleted

    async def health(self) -> dict:
        if self._use_fallback:
            return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}
        client = self._get_client()
        if client:
            try:
                info = client.get_collection(COLLECTION)
                return {"status": "healthy", "mode": "qdrant", "points": info.points_count}
            except Exception:
                return {"status": "unhealthy", "mode": "qdrant"}
        return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not query_vector:
            return []

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    from qdrant_client.models import Filter, FieldCondition, MatchAny
                    search_filter = None
                    if acl_principals:
                        search_filter = Filter(must=[
                            FieldCondition(key="acl_principals", match=MatchAny(any=acl_principals))
                        ])
                    results = client.search(
                        collection_name=COLLECTION,
                        query_vector=query_vector,
                        limit=top_k,
                        query_filter=search_filter,
                        with_payload=True,
                    )
                    return [
                        {"chunk_id": r.id, "score": r.score, "payload": r.payload}
                        for r in results
                    ]
                except Exception as e:
                    logger.error("vector.search_error", error=str(e))

        # Fallback: cosine similarity in-memory
        import math
        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for cid, item in self._fallback.items():
            if acl_principals:
                item_acl = item.get("acl_principals", [])
                if not any(p in item_acl for p in acl_principals) and "public" not in [a.lower() for a in item_acl]:
                    continue
            score = cosine(query_vector, item["vector"])
            scored.append({"chunk_id": cid, "score": score, "payload": item})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
