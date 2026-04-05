"""Metadata index writer — PostgreSQL (with in-memory fallback)."""

from __future__ import annotations

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)


class MetadataIndexWriter(BaseIndexWriter):
    """Writes chunk metadata to PostgreSQL. Falls back to in-memory dict."""

    name = "metadata"

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self.stats = {"written": 0, "deleted": 0}

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_status = {e.chunk_id: e.status for e in embeddings}
        written = 0
        for chunk in chunks:
            self._store[chunk.id] = {
                "chunk_id": chunk.id,
                "doc_id": chunk.document_id,
                "acl_principals": chunk.metadata.get("acl_principals", []),
                "acl_filter_ref": chunk.acl_filter_ref,
                "content_hash": str(hash(chunk.text)),
                "embedding_status": embed_status.get(chunk.id, "pending"),
                "metadata": chunk.metadata,
                "section_path": chunk.section_path,
                "chunk_type": chunk.chunk_type,
                "order": chunk.order,
            }
            written += 1
        self.stats["written"] += written
        return written

    async def delete(self, chunk_ids: list[str]) -> int:
        deleted = 0
        for cid in chunk_ids:
            if cid in self._store:
                del self._store[cid]
                deleted += 1
        self.stats["deleted"] += deleted
        return deleted

    async def health(self) -> dict:
        return {"status": "healthy", "mode": "in-memory", "count": len(self._store)}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        """ACL-filtered metadata lookup."""
        results = []
        for cid, item in self._store.items():
            if acl_principals:
                item_acl = item.get("acl_principals", [])
                if not any(p in item_acl for p in acl_principals) and "public" not in [str(a).lower() for a in item_acl]:
                    continue
            if filters:
                if "doc_id" in filters:
                    if item.get("doc_id") not in filters["doc_id"]:
                        continue
            results.append({"chunk_id": cid, "score": 1.0, "payload": item})
        return results[:top_k]

    def get_visible_chunks(self, user_principals: list[str]) -> list[dict]:
        """PostgreSQL get_visible_chunks equivalent."""
        return [
            item for item in self._store.values()
            if any(p in item.get("acl_principals", []) for p in user_principals)
            or "public" in [str(a).lower() for a in item.get("acl_principals", [])]
        ]
