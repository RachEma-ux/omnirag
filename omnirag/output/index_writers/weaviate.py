"""Weaviate index writer — vector DB with schema (with in-memory fallback)."""

from __future__ import annotations

import math
import os
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)

COLLECTION_NAME = "ChunkEmbeddings"


class WeaviateIndexWriter(BaseIndexWriter):
    """Writes to Weaviate vector DB. Falls back to in-memory store."""

    name = "weaviate"

    def __init__(self) -> None:
        self._client: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = False
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import weaviate
            from weaviate.classes.config import Configure, Property, DataType
            from weaviate.classes.init import Auth

            url = os.environ.get("WEAVIATE_URL", "http://localhost:8080")
            api_key = os.environ.get("WEAVIATE_API_KEY", "")

            if api_key:
                self._client = weaviate.connect_to_custom(
                    http_host=url.replace("http://", "").replace("https://", "").split(":")[0],
                    http_port=int(url.split(":")[-1]) if ":" in url.rsplit("/", 1)[-1] else 8080,
                    http_secure=url.startswith("https"),
                    grpc_host=url.replace("http://", "").replace("https://", "").split(":")[0],
                    grpc_port=50051,
                    grpc_secure=url.startswith("https"),
                    auth_credentials=Auth.api_key(api_key),
                )
            else:
                self._client = weaviate.connect_to_local(
                    host=url.replace("http://", "").replace("https://", "").split(":")[0],
                    port=int(url.split(":")[-1]) if ":" in url.rsplit("/", 1)[-1] else 8080,
                )

            # Create collection schema if not exists
            if not self._client.collections.exists(COLLECTION_NAME):
                self._client.collections.create(
                    name=COLLECTION_NAME,
                    vectorizer_config=Configure.Vectorizer.none(),
                    properties=[
                        Property(name="chunk_id", data_type=DataType.TEXT),
                        Property(name="doc_id", data_type=DataType.TEXT),
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="chunk_type", data_type=DataType.TEXT),
                        Property(name="order_num", data_type=DataType.INT),
                        Property(name="acl_principals", data_type=DataType.TEXT_ARRAY),
                    ],
                )
                logger.info("weaviate.collection_created", collection=COLLECTION_NAME)

            return self._client
        except Exception as e:
            logger.warning("weaviate.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_map = {e.chunk_id: e.vector for e in embeddings if e.status == "completed" and e.vector}
        written = 0

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    collection = client.collections.get(COLLECTION_NAME)
                    with collection.batch.dynamic() as batch:
                        for chunk in chunks:
                            vec = embed_map.get(chunk.id)
                            if not vec:
                                continue
                            batch.add_object(
                                properties={
                                    "chunk_id": chunk.id,
                                    "doc_id": chunk.document_id,
                                    "text": chunk.text[:500],
                                    "chunk_type": chunk.chunk_type,
                                    "order_num": chunk.order,
                                    "acl_principals": chunk.metadata.get("acl_principals", []),
                                },
                                vector=vec,
                                uuid=chunk.id,
                            )
                            written += 1
                    self.stats["written"] += written
                    return written
                except Exception as e:
                    logger.error("weaviate.write_error", error=str(e))
                    self.stats["errors"] += 1
                    self._use_fallback = True

        # In-memory fallback
        written = 0
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
            client = self._get_client()
            if client:
                try:
                    collection = client.collections.get(COLLECTION_NAME)
                    deleted = 0
                    for cid in chunk_ids:
                        try:
                            collection.data.delete_by_id(cid)
                            deleted += 1
                        except Exception:
                            pass
                    self.stats["deleted"] += deleted
                    return deleted
                except Exception as e:
                    logger.error("weaviate.delete_error", error=str(e))
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
        client = self._get_client()
        if client:
            try:
                meta = client.get_meta()
                return {
                    "status": "healthy",
                    "mode": "weaviate",
                    "version": meta.get("version", "unknown"),
                }
            except Exception:
                return {"status": "unhealthy", "mode": "weaviate"}
        return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not query_vector:
            return []

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    from weaviate.classes.query import MetadataQuery, Filter

                    collection = client.collections.get(COLLECTION_NAME)

                    where_filter = None
                    if acl_principals:
                        where_filter = Filter.by_property("acl_principals").contains_any(acl_principals)

                    results = collection.query.near_vector(
                        near_vector=query_vector,
                        limit=top_k,
                        filters=where_filter,
                        return_metadata=MetadataQuery(distance=True),
                    )

                    return [
                        {
                            "chunk_id": str(obj.uuid),
                            "score": 1.0 - (obj.metadata.distance or 0.0),
                            "payload": obj.properties,
                        }
                        for obj in results.objects
                    ]
                except Exception as e:
                    logger.error("weaviate.search_error", error=str(e))

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
