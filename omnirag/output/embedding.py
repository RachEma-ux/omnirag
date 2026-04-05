"""Embedding pipeline — chunks → vectors, batched, with retry and DLQ."""

from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog

from omnirag.intake.models import Chunk

logger = structlog.get_logger(__name__)

BATCH_SIZE = 256
MAX_RETRIES = 3
BACKOFF_BASE_MS = 100


@dataclass
class EmbeddingResult:
    chunk_id: str
    vector: list[float]
    status: str = "completed"
    error: str | None = None


@dataclass
class EmbeddingDLQ:
    """Dead-letter queue for failed embeddings."""
    entries: list[dict] = field(default_factory=list)

    def add(self, chunk_id: str, error: str) -> None:
        self.entries.append({"chunk_id": chunk_id, "error": error, "timestamp": time.time()})

    def list(self) -> list[dict]:
        return self.entries

    def count(self) -> int:
        return len(self.entries)


class EmbeddingPipeline:
    """Generates embeddings for chunks, writes to vector DB.

    Model: all-MiniLM-L6-v2 (384-dim) via sentence-transformers.
    Batch: 256 chunks per batch.
    Retry: exponential backoff (100, 200, 400ms), max 3 attempts.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", vector_dim: int = 384) -> None:
        self.model_name = model_name
        self.vector_dim = vector_dim
        self._model: Any = None
        self.dlq = EmbeddingDLQ()
        self.stats = {"total": 0, "completed": 0, "failed": 0}

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning("embedding.no_model", msg="sentence-transformers not installed, using random vectors")
                self._model = "fallback"
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        if model == "fallback":
            import random
            return [[random.gauss(0, 0.1) for _ in range(self.vector_dim)] for _ in texts]
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

    async def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        """Embed a list of chunks in batches with retry."""
        results: list[EmbeddingResult] = []

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [c.text for c in batch]

            for attempt in range(MAX_RETRIES):
                try:
                    vectors = self._encode(texts)
                    for chunk, vector in zip(batch, vectors):
                        results.append(EmbeddingResult(chunk_id=chunk.id, vector=vector))
                        self.stats["completed"] += 1
                    self.stats["total"] += len(batch)
                    break
                except Exception as e:
                    delay = BACKOFF_BASE_MS * (2 ** attempt) / 1000
                    logger.warning("embedding.retry", attempt=attempt + 1, delay=delay, error=str(e))
                    await asyncio.sleep(delay)

                    if attempt == MAX_RETRIES - 1:
                        for chunk in batch:
                            results.append(EmbeddingResult(chunk_id=chunk.id, vector=[], status="failed", error=str(e)))
                            self.dlq.add(chunk.id, str(e))
                            self.stats["failed"] += 1
                        self.stats["total"] += len(batch)

        return results

    def get_stats(self) -> dict:
        return {**self.stats, "dlq_count": self.dlq.count(), "model": self.model_name, "vector_dim": self.vector_dim}


_pipeline = EmbeddingPipeline()


def get_embedding_pipeline() -> EmbeddingPipeline:
    return _pipeline
