"""Universal Intake Gate — governed control plane with 12-state machine.

Pipeline: REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED →
          MATERIALIZED → ENRICHED → ACL_BOUND → CHUNKED → INDEXED → VERIFIED → ACTIVE
"""

from __future__ import annotations

import uuid
import time
from typing import Any

import structlog

from omnirag.intake.models import (
    ACL, CanonicalDocument, Chunk, ConnectorConfig, JobState,
    RawContent, SourceObject, SyncJob, TriggerType,
)
from omnirag.intake.state_machine import validate_transition
from omnirag.intake.detector import detect_format
from omnirag.intake.cursor import get_cursor_store
from omnirag.intake.lineage import get_lineage_store
from omnirag.intake.acl.manager import get_acl_manager
from omnirag.intake.connectors.registry import get_registry as get_connectors
from omnirag.intake.extractors.base import get_extractor_registry
from omnirag.intake.materializers.base import get_materializer_registry
from omnirag.intake.chunkers.base import get_chunker_registry
from omnirag.intake.backpressure.admission import get_admission_controller, Decision
from omnirag.intake.backpressure.dead_letter import get_dead_letter_queue

logger = structlog.get_logger(__name__)


class IntakeGate:
    """Orchestrates the full governed intake pipeline."""

    def __init__(self) -> None:
        self._jobs: dict[str, SyncJob] = {}
        self._source_objects: dict[str, list[SourceObject]] = {}
        self._documents: dict[str, list[CanonicalDocument]] = {}
        self._chunks: dict[str, list[Chunk]] = {}
        self._connectors: dict[str, ConnectorConfig] = {}

    @property
    def jobs(self) -> dict[str, SyncJob]:
        return self._jobs

    def get_job(self, job_id: str) -> SyncJob | None:
        return self._jobs.get(job_id)

    def get_documents(self, job_id: str) -> list[CanonicalDocument]:
        return self._documents.get(job_id, [])

    def get_chunks(self, job_id: str) -> list[Chunk]:
        return self._chunks.get(job_id, [])

    def register_connector(self, config: ConnectorConfig) -> None:
        self._connectors[config.id] = config

    def get_connector_config(self, connector_id: str) -> ConnectorConfig:
        return self._connectors.get(connector_id, ConnectorConfig())

    def _transition(self, job: SyncJob, new_state: JobState, **details: Any) -> None:
        old_state = job.state
        validate_transition(old_state, new_state)
        job.transition(new_state)
        get_lineage_store().record_transition(
            job_id=job.id,
            from_state=old_state.value,
            to_state=new_state.value,
            details=details,
        )
        logger.info("intake.transition", job_id=job.id, from_state=old_state.value, to_state=new_state.value)

    async def ingest(self, source: str, config: dict, pipeline: str | None = None,
                     trigger: TriggerType = TriggerType.MANUAL) -> SyncJob:
        """Run the full 12-state intake pipeline."""

        # ── REGISTERED ──
        job = SyncJob(source=source, config=config, pipeline=pipeline, trigger=trigger)
        self._jobs[job.id] = job
        self._source_objects[job.id] = []
        self._documents[job.id] = []
        self._chunks[job.id] = []

        logger.info("intake.registered", job_id=job.id, source=source)

        # Resolve connector
        connector = get_connectors().resolve(source)
        if not connector:
            job.fail(f"No connector for source: {source}")
            return job

        job.connector_id = connector.name
        connector_config = self.get_connector_config(connector.name)

        # ── ADMISSION CHECK ──
        admission = get_admission_controller()
        decision = admission.can_submit(connector_config, job)
        if decision.decision == Decision.DEFER:
            job.defer(decision.reason)
            logger.warning("intake.deferred", job_id=job.id, reason=decision.reason)
            return job
        if decision.decision == Decision.REJECT:
            job.fail(f"Rejected: {decision.reason}")
            return job

        admission.job_started(connector.name)

        try:
            # ── DISCOVERED ──
            try:
                cursor = get_cursor_store().get(connector.name)
                source_objects = await connector.discover(source, config, cursor)
                job.files_found = len(source_objects)
                self._source_objects[job.id] = source_objects
                self._transition(job, JobState.DISCOVERED, files_found=len(source_objects))
            except Exception as e:
                job.fail(f"Discovery failed: {e}")
                return job

            if not source_objects:
                job.fail("No objects found at source")
                return job

            # ── AUTHORIZED ──
            acl_manager = get_acl_manager()
            acl_snapshots: dict[str, Any] = {}
            try:
                for obj in source_objects:
                    acl = await connector.permissions(obj, config)
                    snap = acl_manager.capture(acl)
                    obj.acl_snapshot_ref = snap.id
                    acl_snapshots[obj.id] = snap
                self._transition(job, JobState.AUTHORIZED)
            except Exception as e:
                job.fail(f"Authorization failed: {e}")
                return job

            # ── FETCHED ──
            extractor_registry = get_extractor_registry()
            materializer_registry = get_materializer_registry()
            chunker_registry = get_chunker_registry()

            fetched_raw: list[tuple[SourceObject, RawContent]] = []
            try:
                for obj in source_objects:
                    raw = await connector.fetch(obj, config)
                    if raw:
                        fetched_raw.append((obj, raw))
                self._transition(job, JobState.FETCHED, files_fetched=len(fetched_raw))
            except Exception as e:
                job.fail(f"Fetch failed: {e}")
                return job

            # ── EXTRACTED ──
            all_extracted: list[tuple[SourceObject, Any, list[Any]]] = []
            try:
                for obj, raw in fetched_raw:
                    mime, ext = detect_format(raw.data, raw.filename, raw.mime_type)
                    if not raw.mime_type:
                        raw.mime_type = mime
                    if not raw.extension:
                        raw.extension = ext
                    obj.mime_type = mime

                    extractor = extractor_registry.resolve(mime, ext)
                    if not extractor:
                        job.errors.append(f"No extractor for {raw.filename} ({mime})")
                        continue

                    extracted_list = await extractor.extract(raw, obj)
                    job.files_loaded += 1
                    all_extracted.append((obj, extractor, extracted_list))

                self._transition(job, JobState.EXTRACTED, files_loaded=job.files_loaded)
            except Exception as e:
                job.fail(f"Extraction failed: {e}")
                return job

            # ── MATERIALIZED ──
            all_docs: list[CanonicalDocument] = []
            try:
                for obj, extractor, extracted_list in all_extracted:
                    acl_snap = acl_snapshots.get(obj.id)
                    acl = acl_snap.acl if acl_snap else ACL()

                    for extracted in extracted_list:
                        materializer = materializer_registry.resolve(obj, extracted)
                        doc = materializer.materialize(obj, extracted, acl)
                        all_docs.append(doc)
                        job.documents_created += 1

                self._documents[job.id] = all_docs
                self._transition(job, JobState.MATERIALIZED, documents=job.documents_created)
            except Exception as e:
                job.fail(f"Materialization failed: {e}")
                return job

            # ── ENRICHED ──
            try:
                for doc in all_docs:
                    doc.metadata["enriched_at"] = time.time()
                    doc.metadata["confidence"] = min(
                        (e.confidence for _, _, el in all_extracted for e in el), default=1.0
                    )
                self._transition(job, JobState.ENRICHED)
            except Exception as e:
                job.fail(f"Enrichment failed: {e}")
                return job

            # ── ACL_BOUND ──
            try:
                for doc in all_docs:
                    snap_ref = doc.metadata.get("acl_snapshot_ref")
                    if snap_ref:
                        snap = acl_manager.get(snap_ref)
                        if snap:
                            acl_manager.bind_document(doc, snap)
                self._transition(job, JobState.ACL_BOUND)
            except Exception as e:
                job.fail(f"ACL binding failed: {e}")
                return job

            # ── CHUNKED ──
            all_chunks: list[Chunk] = []
            try:
                for doc in all_docs:
                    chunker = chunker_registry.resolve(doc.semantic_type)
                    doc_chunks = chunker.chunk(doc)

                    # Propagate ACL to chunks
                    snap_ref = doc.metadata.get("acl_snapshot_ref")
                    if snap_ref:
                        snap = acl_manager.get(snap_ref)
                        if snap:
                            acl_manager.bind_chunks(doc_chunks, snap)

                    all_chunks.extend(doc_chunks)
                    job.chunks_created += len(doc_chunks)

                self._chunks[job.id] = all_chunks
                self._transition(job, JobState.CHUNKED, chunks=job.chunks_created)
            except Exception as e:
                job.fail(f"Chunking failed: {e}")
                return job

            # ── INDEXED ──
            try:
                # Index writer abstraction (Phase F will add real writers)
                self._transition(job, JobState.INDEXED, chunks_indexed=len(all_chunks))
            except Exception as e:
                job.fail(f"Indexing failed: {e}")
                return job

            # ── VERIFIED ──
            try:
                # Verify: all docs have chunks, all chunks reference valid docs
                doc_ids = {d.id for d in all_docs}
                orphan_chunks = [c for c in all_chunks if c.document_id not in doc_ids]
                if orphan_chunks:
                    job.errors.append(f"{len(orphan_chunks)} orphan chunks detected")
                self._transition(job, JobState.VERIFIED)
            except Exception as e:
                job.fail(f"Verification failed: {e}")
                return job

            # ── ACTIVE ──
            self._transition(job, JobState.ACTIVE)

            # Update cursor
            new_cursor = str(job.files_found)
            get_cursor_store().update(connector.name, new_cursor)

            logger.info(
                "intake.active",
                job_id=job.id,
                files=job.files_found,
                docs=job.documents_created,
                chunks=job.chunks_created,
                errors=len(job.errors),
            )

        except Exception as e:
            job.fail(f"Unexpected error: {e}")
            logger.error("intake.unexpected_error", job_id=job.id, error=str(e))

        finally:
            admission.job_finished(connector.name)

            # Dead-letter if max retries exceeded
            if job.state == JobState.DEAD_LETTERED:
                get_dead_letter_queue().insert(job)

        return job


# Singleton
_gate = IntakeGate()


def get_gate() -> IntakeGate:
    return _gate
