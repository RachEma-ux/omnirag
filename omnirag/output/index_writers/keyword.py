"""Keyword index writer — Elasticsearch (with PostgreSQL FTS fallback)."""

from __future__ import annotations

import os
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)

INDEX_NAME = "chunks"


class KeywordIndexWriter(BaseIndexWriter):
    """BM25 keyword search via Elasticsearch. Falls back to in-memory text matching."""

    name = "keyword"

    def __init__(self) -> None:
        self._client: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = False
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from elasticsearch import Elasticsearch
            url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
            self._client = Elasticsearch(url, request_timeout=10)
            if not self._client.indices.exists(index=INDEX_NAME):
                self._client.indices.create(index=INDEX_NAME, body={
                    "settings": {"number_of_shards": 2, "number_of_replicas": 1, "refresh_interval": "1s",
                                 "analysis": {"analyzer": {"default": {"type": "english"}}}},
                    "mappings": {"properties": {
                        "chunk_id": {"type": "keyword"}, "doc_id": {"type": "keyword"},
                        "content": {"type": "text", "analyzer": "english"},
                        "acl_principals": {"type": "keyword"},
                        "metadata": {"type": "object", "enabled": True},
                        "created_at": {"type": "date"},
                    }},
                })
            return self._client
        except Exception as e:
            logger.warning("keyword.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        written = 0

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    actions = []
                    for chunk in chunks:
                        actions.append({"index": {"_index": INDEX_NAME, "_id": chunk.id}})
                        actions.append({
                            "chunk_id": chunk.id,
                            "doc_id": chunk.document_id,
                            "content": chunk.text,
                            "acl_principals": chunk.metadata.get("acl_principals", []),
                            "metadata": chunk.metadata,
                        })
                    if actions:
                        client.bulk(body=actions)
                        written = len(chunks)
                        self.stats["written"] += written
                    return written
                except Exception as e:
                    logger.error("keyword.write_error", error=str(e))
                    self.stats["errors"] += 1
                    self._use_fallback = True

        # In-memory fallback
        for chunk in chunks:
            self._fallback[chunk.id] = {
                "chunk_id": chunk.id,
                "doc_id": chunk.document_id,
                "content": chunk.text,
                "acl_principals": chunk.metadata.get("acl_principals", []),
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
                info = client.cat.indices(index=INDEX_NAME, format="json")
                return {"status": "healthy", "mode": "elasticsearch", "docs": info[0]["docs.count"] if info else 0}
            except Exception:
                return {"status": "unhealthy", "mode": "elasticsearch"}
        return {"status": "fallback", "mode": "in-memory", "count": len(self._fallback)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not query_text:
            return []

        if not self._use_fallback:
            client = self._get_client()
            if client:
                try:
                    body: dict[str, Any] = {"size": top_k, "query": {"bool": {
                        "must": {"match": {"content": query_text}},
                    }}}
                    if acl_principals:
                        body["query"]["bool"]["filter"] = {"terms": {"acl_principals": acl_principals}}
                    result = client.search(index=INDEX_NAME, body=body)
                    return [
                        {"chunk_id": hit["_id"], "score": hit["_score"], "payload": hit["_source"]}
                        for hit in result["hits"]["hits"]
                    ]
                except Exception as e:
                    logger.error("keyword.search_error", error=str(e))

        # Fallback: simple text matching
        query_lower = query_text.lower()
        terms = query_lower.split()
        scored = []
        for cid, item in self._fallback.items():
            if acl_principals:
                item_acl = item.get("acl_principals", [])
                if not any(p in item_acl for p in acl_principals) and "public" not in [a.lower() for a in item_acl]:
                    continue
            content_lower = item["content"].lower()
            score = sum(1 for t in terms if t in content_lower) / max(len(terms), 1)
            if score > 0:
                scored.append({"chunk_id": cid, "score": score, "payload": item})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
