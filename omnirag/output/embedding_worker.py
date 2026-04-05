"""Async embedding worker — background task queue with batch processing."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from omnirag.intake.models import Chunk
from omnirag.output.embedding import get_embedding_pipeline, EmbeddingResult
from omnirag.output.index_writers.base import get_writer_registry
from omnirag.output.consistency import get_consistency_coordinator

logger = structlog.get_logger(__name__)

BATCH_SIZE = 256
FLUSH_INTERVAL = 5.0  # seconds
MAX_RETRIES = 3


@dataclass
class EmbeddingJob:
    chunks: list[Chunk]
    callback: Any = None
    submitted_at: float = field(default_factory=time.time)


class EmbeddingWorker:
    """Background worker: consumes chunks from queue, embeds in batches, writes to stores."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[EmbeddingJob] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._task: asyncio.Task | None = None
        self.stats = {
            "submitted": 0, "embedded": 0, "written": 0,
            "failed": 0, "batches": 0, "dlq": 0,
        }

    async def start(self) -> None:
        """Start the background worker loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("embedding_worker.started")

    async def stop(self) -> None:
        """Stop the worker and flush remaining items."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("embedding_worker.stopped")

    async def submit(self, chunks: list[Chunk]) -> None:
        """Submit chunks for async embedding."""
        if not chunks:
            return
        job = EmbeddingJob(chunks=chunks)
        await self._queue.put(job)
        self.stats["submitted"] += len(chunks)

    async def _worker_loop(self) -> None:
        """Main worker loop: accumulate batches, embed, write."""
        buffer: list[Chunk] = []
        last_flush = time.monotonic()

        while self._running:
            try:
                # Drain queue with timeout
                try:
                    job = await asyncio.wait_for(self._queue.get(), timeout=FLUSH_INTERVAL)
                    buffer.extend(job.chunks)
                except asyncio.TimeoutError:
                    pass

                # Flush if batch full or time elapsed
                should_flush = (
                    len(buffer) >= BATCH_SIZE or
                    (buffer and time.monotonic() - last_flush >= FLUSH_INTERVAL)
                )

                if should_flush and buffer:
                    batch = buffer[:BATCH_SIZE]
                    buffer = buffer[BATCH_SIZE:]
                    await self._process_batch(batch)
                    last_flush = time.monotonic()

            except asyncio.CancelledError:
                # Flush remaining on shutdown
                if buffer:
                    await self._process_batch(buffer)
                raise
            except Exception as e:
                logger.error("embedding_worker.error", error=str(e))
                await asyncio.sleep(1)

    async def _process_batch(self, chunks: list[Chunk]) -> None:
        """Embed a batch and write to all index stores."""
        pipeline = get_embedding_pipeline()
        registry = get_writer_registry()
        coordinator = get_consistency_coordinator()

        for attempt in range(MAX_RETRIES):
            try:
                # Embed
                results = await pipeline.embed_chunks(chunks)
                self.stats["embedded"] += len([r for r in results if r.status == "completed"])
                self.stats["failed"] += len([r for r in results if r.status == "failed"])

                # Write to all stores
                stores_written = []
                for writer in registry.all():
                    try:
                        count = await writer.write(chunks, results)
                        if count > 0:
                            stores_written.append(writer.name)
                    except Exception as e:
                        logger.error("embedding_worker.write_error", writer=writer.name, error=str(e))

                self.stats["written"] += len(chunks)
                self.stats["batches"] += 1

                # Commit consistency version
                if stores_written:
                    coordinator.commit_batch(stores_written)

                return  # Success

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = 0.5 * (2 ** attempt)
                    logger.warning("embedding_worker.retry", attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(delay)
                else:
                    logger.error("embedding_worker.batch_failed", error=str(e))
                    self.stats["dlq"] += len(chunks)

    def get_stats(self) -> dict:
        return {**self.stats, "queue_size": self._queue.qsize(), "running": self._running}


_worker = EmbeddingWorker()


def get_embedding_worker() -> EmbeddingWorker:
    return _worker
