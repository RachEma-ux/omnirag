"""Hybrid retrieval — parallel vector + keyword search, RRF fusion, reranking, fallback."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from omnirag.output.embedding import get_embedding_pipeline
from omnirag.output.index_writers.base import get_writer_registry

logger = structlog.get_logger(__name__)

RRF_K = 60
CANDIDATE_MULTIPLIER = 2
FALLBACK_TIMEOUT_MS = 5000


@dataclass
class RetrievalResult:
    chunk_id: str
    doc_id: str
    content: str
    score: float
    retrieval_scores: dict = field(default_factory=dict)


@dataclass
class EvidenceBundle:
    """Internal retrieval result before generation."""
    mode: str = "hybrid"
    chunks: list[RetrievalResult] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None
    latency_ms: float = 0


def rrf(ranked_lists: list[list[dict]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — combines ranked lists from multiple retrievers."""
    scores: dict[str, float] = {}
    for rank_list in ranked_lists:
        for rank, item in enumerate(rank_list):
            cid = item["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    """Parallel hybrid search with RRF fusion, reranking, ACL filtering, and fallback."""

    def __init__(self, rerank_enabled: bool = True) -> None:
        self.rerank_enabled = rerank_enabled
        self._reranker: Any = None

    def _get_reranker(self) -> Any:
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            return self._reranker
        except ImportError:
            logger.warning("reranker.unavailable", msg="sentence-transformers not installed")
            return None

    async def retrieve(self, query: str, acl_principals: list[str],
                       top_k: int = 10, filters: dict | None = None,
                       read_your_writes: bool = True) -> EvidenceBundle:
        start = time.monotonic()
        registry = get_writer_registry()
        vector_writer = registry.get("vector")
        keyword_writer = registry.get("keyword")

        # Generate query embedding
        pipeline = get_embedding_pipeline()
        from omnirag.intake.models import Chunk
        dummy = Chunk(text=query)
        embed_results = await pipeline.embed_chunks([dummy])
        query_vector = embed_results[0].vector if embed_results and embed_results[0].vector else None

        candidate_k = top_k * CANDIDATE_MULTIPLIER
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        mode = "hybrid"
        fallback_used = False
        fallback_reason = None

        # Parallel search
        vector_ok = False
        keyword_ok = False

        if vector_writer and query_vector:
            try:
                vector_results = await asyncio.wait_for(
                    vector_writer.search(query_vector, None, acl_principals, candidate_k, filters),
                    timeout=FALLBACK_TIMEOUT_MS / 1000,
                )
                vector_ok = True
            except Exception as e:
                logger.warning("retrieval.vector_down", error=str(e))
                fallback_reason = f"vector-down: {e}"

        if keyword_writer:
            try:
                keyword_results = await asyncio.wait_for(
                    keyword_writer.search(None, query, acl_principals, candidate_k, filters),
                    timeout=FALLBACK_TIMEOUT_MS / 1000,
                )
                keyword_ok = True
            except Exception as e:
                logger.warning("retrieval.keyword_down", error=str(e))
                fallback_reason = f"keyword-down: {e}"

        # Fallback matrix
        if not vector_ok and not keyword_ok:
            return EvidenceBundle(
                mode="unavailable", fallback_used=True, fallback_reason="both stores down",
                latency_ms=(time.monotonic() - start) * 1000,
            )
        elif not vector_ok:
            mode = "keyword_only"
            fallback_used = True
        elif not keyword_ok:
            mode = "vector_only"
            fallback_used = True

        # RRF fusion
        if vector_results and keyword_results:
            fused = rrf([vector_results, keyword_results])
        elif vector_results:
            fused = [(r["chunk_id"], r["score"]) for r in vector_results]
        else:
            fused = [(r["chunk_id"], r["score"]) for r in keyword_results]

        # Build result map
        all_items = {r["chunk_id"]: r for r in vector_results + keyword_results}

        # Get top candidates for reranking
        top_candidates = fused[:50]

        # Reranking
        if self.rerank_enabled and len(top_candidates) > 0:
            reranker = self._get_reranker()
            if reranker:
                try:
                    passages = []
                    candidate_ids = []
                    for cid, _ in top_candidates:
                        item = all_items.get(cid)
                        if item:
                            text = item.get("payload", {}).get("text") or item.get("payload", {}).get("content", "")
                            passages.append(text[:1000])
                            candidate_ids.append(cid)

                    if passages:
                        scores = reranker.predict([(query, p) for p in passages])
                        ranked = sorted(zip(candidate_ids, scores), key=lambda x: x[1], reverse=True)
                        fused = [(cid, float(score)) for cid, score in ranked]
                except Exception as e:
                    logger.warning("reranker.failed", error=str(e))
                    fallback_reason = (fallback_reason or "") + f"; reranker-down: {e}"
                    fallback_used = True

        # Build final results
        chunks: list[RetrievalResult] = []
        for cid, score in fused[:top_k]:
            item = all_items.get(cid, {})
            payload = item.get("payload", {})
            chunks.append(RetrievalResult(
                chunk_id=cid,
                doc_id=payload.get("doc_id", ""),
                content=payload.get("text") or payload.get("content", ""),
                score=score,
                retrieval_scores={
                    "vector": next((r["score"] for r in vector_results if r["chunk_id"] == cid), None),
                    "bm25": next((r["score"] for r in keyword_results if r["chunk_id"] == cid), None),
                    "rrf": score,
                },
            ))

        return EvidenceBundle(
            mode=mode,
            chunks=chunks,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            latency_ms=(time.monotonic() - start) * 1000,
        )


_retriever = HybridRetriever()


def get_retriever() -> HybridRetriever:
    return _retriever
