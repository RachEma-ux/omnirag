"""Pinecone index writer — managed vector DB (with in-memory fallback)."""

from __future__ import annotations

import math
import os
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)

VECTOR_DIM = 384


class PineconeIndexWriter(BaseIndexWriter):
    """Writes to Pinecone vector DB. Falls back to in-memory store."""

    name = "pinecone"

    def __init__(self) -> None:
        self._client: Any = None
        self._index: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = False
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    def _get_client(self) -> Any:
        if self._index is not None:
            return self._index
        try:
            from pinecone import Pinecone, ServerlessSpec

            api_key = os.environ.get("PINECONE_API_KEY", "")
            index_name = os.environ.get("PINECONE_INDEX", "chunk-embeddings")
            environment = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")

            if not api_key:
                raise ValueError("PINECONE_API_KEY not set")

            self._client = Pinecone(api_key=api_key)

            # Create index if it does not exist
            existing = [idx.name for idx in self._client.list_indexes()]
            if index_name not in existing:
                self._client.create_index(
                    name=index_name,
                    dimension=VECTOR_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region=environment),
                )
                logger.info("pinecone.index_created", index=index_name)

            self._index = self._client.Index(index_name)
            return self._index
        except Exception as e:
            logger.warning("pinecone.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_map = {e.chunk_id: e.vector for e in embeddings if e.status == "completed" and e.vector}
        written = 0

        if not self._use_fallback:
            index = self._get_client()
            if index:
                try:
                    vectors = []
                    for chunk in chunks:
                        vec = embed_map.get(chunk.id)
                        if not vec:
                            continue
                        vectors.append({
                            "id": chunk.id,
                            "values": vec,
                            "metadata": {
                                "chunk_id": chunk.id,
                                "doc_id": chunk.document_id,
                                "acl_principals": chunk.metadata.get("acl_principals", []),
                                "text": chunk.text[:500],
                                "chunk_type": chunk.chunk_type,
                                "order": chunk.order,
                            },
                        })
                    if vectors:
                        # Pinecone upsert in batches of 100
                        batch_size = 100
                        for i in range(0, len(vectors), batch_size):
                            index.upsert(vectors=vectors[i:i + batch_size])
                        written = len(vectors)
                        self.stats["written"] += written
                    return written
                except Exception as e:
                    logger.error("pinecone.write_error", error=str(e))
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
        if not self._use_fallback:
            index = self._get_client()
            if index:
                try:
                    index.delete(ids=chunk_ids)
                    self.stats["deleted"] += len(chunk_ids)
                    return len(chunk_ids)
                except Exception as e:
                    logger.error("pinecone.delete_error", error=str(e))
                    self.stats["errors"] += 1
                    self._use_fallback = True

        # Fallback
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
        index = self._get_client()
        if index:
            try:
                stats = index.describe_index_stats()
                return {
                    "status": "healthy",
                    "mode": "pinecone",
                    "total_vectors": stats.total_vector_count,
                    "namespaces": len(stats.namespaces),
                }
            except Exception:
                return {"status": "unhealthy", "mode": "pinecone"}
        return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not query_vector:
            return []

        if not self._use_fallback:
            index = self._get_client()
            if index:
                try:
                    query_filter = None
                    if acl_principals:
                        query_filter = {
                            "acl_principals": {"$in": acl_principals},
                        }
                    results = index.query(
                        vector=query_vector,
                        top_k=top_k,
                        include_metadata=True,
                        filter=query_filter,
                    )
                    return [
                        {"chunk_id": m.id, "score": m.score, "payload": m.metadata or {}}
                        for m in results.matches
                    ]
                except Exception as e:
                    logger.error("pinecone.search_error", error=str(e))

        # Fallback: cosine similarity in-memory
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
