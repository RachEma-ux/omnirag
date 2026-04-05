"""pgvector index writer — PostgreSQL as vector store (single DB for vectors + FTS + metadata)."""

from __future__ import annotations

import os
import math
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult
from omnirag.output.index_writers.base import BaseIndexWriter

logger = structlog.get_logger(__name__)


class PgVectorIndexWriter(BaseIndexWriter):
    """PostgreSQL + pgvector for vector search + full-text search in one DB.

    Falls back to in-memory when PostgreSQL/pgvector unavailable.
    """

    name = "pgvector"

    def __init__(self) -> None:
        self._pool: Any = None
        self._fallback: dict[str, dict] = {}
        self._use_fallback = True
        self.stats = {"written": 0, "deleted": 0, "errors": 0}

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        try:
            import asyncpg
            from omnirag.config.ports import DATABASE_URL
            dsn = os.environ.get("DATABASE_URL", DATABASE_URL)
            self._pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
            # Ensure pgvector extension and table
            async with self._pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS pgvector_chunks (
                        id TEXT PRIMARY KEY,
                        doc_id TEXT,
                        text TEXT,
                        embedding vector(384),
                        acl_principals TEXT[] DEFAULT '{}',
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pgvector_chunks_embedding
                    ON pgvector_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
                """)
                await conn.execute("""
                    ALTER TABLE pgvector_chunks ADD COLUMN IF NOT EXISTS
                    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
                """)
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_pgvector_fts ON pgvector_chunks USING GIN (fts)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_pgvector_acl ON pgvector_chunks USING GIN (acl_principals)")
            self._use_fallback = False
            logger.info("pgvector.connected")
            return self._pool
        except Exception as e:
            logger.warning("pgvector.fallback", error=str(e))
            self._use_fallback = True
            return None

    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        embed_map = {e.chunk_id: e.vector for e in embeddings if e.status == "completed" and e.vector}
        pool = await self._get_pool()

        if pool and not self._use_fallback:
            try:
                async with pool.acquire() as conn:
                    for chunk in chunks:
                        vec = embed_map.get(chunk.id)
                        if not vec:
                            continue
                        vec_str = "[" + ",".join(str(v) for v in vec) + "]"
                        acl = chunk.metadata.get("acl_principals", [])
                        await conn.execute("""
                            INSERT INTO pgvector_chunks (id, doc_id, text, embedding, acl_principals, metadata)
                            VALUES ($1, $2, $3, $4::vector, $5, $6::jsonb)
                            ON CONFLICT (id) DO UPDATE SET text=$3, embedding=$4::vector, acl_principals=$5, metadata=$6::jsonb
                        """, chunk.id, chunk.document_id, chunk.text, vec_str, acl, "{}")
                self.stats["written"] += len(chunks)
                return len(chunks)
            except Exception as e:
                logger.error("pgvector.write_error", error=str(e))
                self.stats["errors"] += 1
                self._use_fallback = True

        # Fallback
        for chunk in chunks:
            vec = embed_map.get(chunk.id)
            if vec:
                self._fallback[chunk.id] = {"vector": vec, "text": chunk.text, "doc_id": chunk.document_id,
                                             "acl_principals": chunk.metadata.get("acl_principals", [])}
        self.stats["written"] += len(chunks)
        return len(chunks)

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
        return {"status": "healthy", "mode": "pgvector"}

    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        pool = await self._get_pool()
        if pool and not self._use_fallback:
            try:
                async with pool.acquire() as conn:
                    results = []
                    # Vector search
                    if query_vector:
                        vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
                        rows = await conn.fetch("""
                            SELECT id, doc_id, text, 1 - (embedding <=> $1::vector) as score
                            FROM pgvector_chunks
                            WHERE acl_principals && $2
                            ORDER BY embedding <=> $1::vector
                            LIMIT $3
                        """, vec_str, acl_principals or ["public"], top_k)
                        results = [{"chunk_id": r["id"], "score": float(r["score"]),
                                    "payload": {"doc_id": r["doc_id"], "text": r["text"][:500]}} for r in rows]

                    # Full-text search (combine if both)
                    if query_text and not results:
                        rows = await conn.fetch("""
                            SELECT id, doc_id, text, ts_rank(fts, plainto_tsquery('english', $1)) as score
                            FROM pgvector_chunks
                            WHERE fts @@ plainto_tsquery('english', $1)
                            AND acl_principals && $2
                            ORDER BY score DESC LIMIT $3
                        """, query_text, acl_principals or ["public"], top_k)
                        results = [{"chunk_id": r["id"], "score": float(r["score"]),
                                    "payload": {"doc_id": r["doc_id"], "text": r["text"][:500]}} for r in rows]
                    return results
            except Exception as e:
                logger.error("pgvector.search_error", error=str(e))

        # Fallback: in-memory cosine
        if not query_vector:
            return []
        def cosine(a, b):
            dot = sum(x*y for x, y in zip(a, b))
            na = math.sqrt(sum(x*x for x in a))
            nb = math.sqrt(sum(x*x for x in b))
            return dot / (na * nb) if na and nb else 0

        scored = []
        for cid, item in self._fallback.items():
            if acl_principals:
                item_acl = item.get("acl_principals", [])
                if not any(p in item_acl for p in acl_principals) and "public" not in [str(a).lower() for a in item_acl]:
                    continue
            score = cosine(query_vector, item["vector"])
            scored.append({"chunk_id": cid, "score": score, "payload": item})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
