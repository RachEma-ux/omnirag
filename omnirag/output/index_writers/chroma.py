"""ChromaDB index writer — embedding database (with in-memory fallback)."""

from __future__ import annotations

import math
import os
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)

COLLECTION_NAME = "chunk_embeddings"


class ChromaIndexWriter(BaseIndexWriter):
    """Writes to ChromaDB. Falls back to in-memory store."""

    name = "chroma"

    def __init__(self) -> None:
        self._client: Any = None
        self._collection: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = False
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    def _get_client(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            import chromadb

            host = os.environ.get("CHROMA_HOST", "")
            port = int(os.environ.get("CHROMA_PORT", "8000"))
            persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "")

            if host:
                self._client = chromadb.HttpClient(host=host, port=port)
                logger.info("chroma.http_client", host=host, port=port)
            elif persist_dir:
                self._client = chromadb.PersistentClient(path=persist_dir)
                logger.info("chroma.persistent_client", path=persist_dir)
            else:
                self._client = chromadb.EphemeralClient()
                logger.info("chroma.ephemeral_client")

            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            return self._collection
        except Exception as e:
            logger.warning("chroma.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_map = {e.chunk_id: e.vector for e in embeddings if e.status == "completed" and e.vector}
        written = 0

        if not self._use_fallback:
            collection = self._get_client()
            if collection:
                try:
                    ids = []
                    vectors = []
                    documents = []
                    metadatas = []

                    for chunk in chunks:
                        vec = embed_map.get(chunk.id)
                        if not vec:
                            continue
                        ids.append(chunk.id)
                        vectors.append(vec)
                        documents.append(chunk.text[:500])
                        metadatas.append({
                            "chunk_id": chunk.id,
                            "doc_id": chunk.document_id,
                            "acl_principals": ",".join(chunk.metadata.get("acl_principals", [])),
                            "chunk_type": chunk.chunk_type,
                            "order": chunk.order,
                        })

                    if ids:
                        collection.upsert(
                            ids=ids,
                            embeddings=vectors,
                            documents=documents,
                            metadatas=metadatas,
                        )
                        written = len(ids)
                        self.stats["written"] += written
                    return written
                except Exception as e:
                    logger.error("chroma.write_error", error=str(e))
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
            collection = self._get_client()
            if collection:
                try:
                    collection.delete(ids=chunk_ids)
                    self.stats["deleted"] += len(chunk_ids)
                    return len(chunk_ids)
                except Exception as e:
                    logger.error("chroma.delete_error", error=str(e))
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
        collection = self._get_client()
        if collection:
            try:
                self._client.heartbeat()
                count = collection.count()
                return {
                    "status": "healthy",
                    "mode": "chroma",
                    "documents": count,
                }
            except Exception:
                return {"status": "unhealthy", "mode": "chroma"}
        return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not query_vector:
            return []

        if not self._use_fallback:
            collection = self._get_client()
            if collection:
                try:
                    where_filter = None
                    if acl_principals:
                        # ChromaDB stores acl_principals as comma-separated string;
                        # use $in on the joined value for each principal
                        where_filter = {
                            "$or": [
                                {"acl_principals": {"$contains": p}}
                                for p in acl_principals
                            ]
                        }

                    query_kwargs: dict[str, Any] = {
                        "query_embeddings": [query_vector],
                        "n_results": top_k,
                        "include": ["metadatas", "documents", "distances"],
                    }
                    if where_filter:
                        query_kwargs["where"] = where_filter

                    results = collection.query(**query_kwargs)

                    output = []
                    if results and results["ids"] and results["ids"][0]:
                        for i, cid in enumerate(results["ids"][0]):
                            distance = results["distances"][0][i] if results["distances"] else 0.0
                            # ChromaDB cosine distance: score = 1 - distance
                            score = 1.0 - distance
                            meta = results["metadatas"][0][i] if results["metadatas"] else {}
                            doc = results["documents"][0][i] if results["documents"] else ""
                            payload = {**meta, "text": doc}
                            output.append({"chunk_id": cid, "score": score, "payload": payload})
                    return output
                except Exception as e:
                    logger.error("chroma.search_error", error=str(e))

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
