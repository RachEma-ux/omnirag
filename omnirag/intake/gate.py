"""Universal Intake Gate — single entry point for all sources and formats."""

from __future__ import annotations

import uuid
import time
import asyncio
from typing import Any

import structlog

from omnirag.intake.models import (
    IntakeJob,
    IntakeRequest,
    IntakeStatus,
    OmniDocument,
    RawContent,
)
from omnirag.intake.detector import detect_format
from omnirag.intake.connectors.registry import get_registry as get_connectors
from omnirag.intake.loaders.registry import get_registry as get_loaders

logger = structlog.get_logger(__name__)


class IntakeGate:
    """Orchestrates: source → connector → loader → normalizer → documents."""

    def __init__(self) -> None:
        self._jobs: dict[str, IntakeJob] = {}
        self._documents: dict[str, list[OmniDocument]] = {}

    @property
    def jobs(self) -> dict[str, IntakeJob]:
        return self._jobs

    def get_job(self, job_id: str) -> IntakeJob | None:
        return self._jobs.get(job_id)

    def get_documents(self, job_id: str) -> list[OmniDocument]:
        return self._documents.get(job_id, [])

    async def ingest(self, request: IntakeRequest) -> IntakeJob:
        """Run the full intake pipeline: resolve → fetch → detect → load → normalize."""
        job_id = f"int_{uuid.uuid4().hex[:12]}"
        job = IntakeJob(id=job_id, request=request)
        self._jobs[job_id] = job
        self._documents[job_id] = []

        logger.info("intake.start", job_id=job_id, source=request.source)

        # 1. Resolve connector
        connector = get_connectors().resolve(request.source)
        if not connector:
            job.fail(f"No connector found for source: {request.source}")
            logger.error("intake.no_connector", source=request.source)
            return job

        job.status = IntakeStatus.FETCHING
        logger.info("intake.connector", connector=connector.name, source=request.source)

        # 2. Fetch raw content
        raw_items: list[RawContent] = []
        try:
            async for raw in connector.fetch(request.source, request.config):
                raw_items.append(raw)
                job.files_found += 1
        except Exception as e:
            job.fail(f"Connector error: {e}")
            logger.error("intake.fetch_error", error=str(e))
            return job

        if not raw_items:
            job.fail("No files found at source")
            return job

        logger.info("intake.fetched", files=job.files_found)

        # 3. Detect format and load each file
        job.status = IntakeStatus.LOADING
        loader_registry = get_loaders()

        for raw in raw_items:
            # Detect format
            mime, ext = detect_format(raw.data, raw.filename, raw.mime_type)
            if not raw.mime_type:
                raw.mime_type = mime
            if not raw.extension:
                raw.extension = ext

            # Find loader
            loader = loader_registry.resolve(mime, ext)
            if not loader:
                job.errors.append(f"No loader for {raw.filename} (mime={mime}, ext={ext})")
                logger.warning("intake.no_loader", filename=raw.filename, mime=mime, ext=ext)
                continue

            # Load
            try:
                segments = await loader.load(raw)
                job.files_loaded += 1

                # Normalize to OmniDocuments
                for segment in segments:
                    doc = OmniDocument.from_segment(segment, connector.name, loader.name)
                    self._documents[job_id].append(doc)
                    job.documents_created += 1

            except Exception as e:
                job.errors.append(f"Loader error for {raw.filename}: {e}")
                logger.error("intake.load_error", filename=raw.filename, error=str(e))

        # 4. Complete
        job.complete()
        logger.info(
            "intake.complete",
            job_id=job_id,
            files_found=job.files_found,
            files_loaded=job.files_loaded,
            documents=job.documents_created,
            errors=len(job.errors),
        )
        return job


# Singleton gate
_gate = IntakeGate()


def get_gate() -> IntakeGate:
    return _gate
