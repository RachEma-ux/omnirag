"""Intake Gate API — full governed control plane endpoints.

Phase G: connectors CRUD, jobs, retry, backpressure, circuit breakers, lineage.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from omnirag.intake.gate import get_gate
from omnirag.intake.models import ConnectorConfig, SyncJob, TriggerType
from omnirag.intake.backpressure.admission import get_admission_controller
from omnirag.intake.backpressure.registry import get_backpressure_registry
from omnirag.intake.backpressure.circuit_breaker import get_circuit_manager
from omnirag.intake.backpressure.dead_letter import get_dead_letter_queue
from omnirag.intake.lineage import get_lineage_store
from omnirag.intake.cursor import get_cursor_store

router = APIRouter()


# ─── Intake (ingest) ───

class IntakeBody(BaseModel):
    source: str
    config: dict = {}
    pipeline: str | None = None
    options: dict = {}

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"source": "/path/to/docs/*.pdf", "config": {"recursive": True}},
                {"source": "https://example.com/report.pdf"},
                {"source": "github://owner/repo/docs", "config": {"token": "ghp_..."}},
                {"source": "s3://bucket/prefix/", "config": {"credentials": {"aws_access_key": "..."}}},
            ]
        }
    }


@router.post("/intake", tags=["intake"])
async def create_intake(body: IntakeBody):
    """Ingest from any source — full 12-state pipeline."""
    gate = get_gate()
    job = await gate.ingest(body.source, body.config, body.pipeline)
    return job.to_dict()


@router.post("/intake/upload", tags=["intake"])
async def upload_file(file: UploadFile = File(...)):
    """Upload a file directly for ingestion via the browser file picker."""
    # Save uploaded file to temp directory
    tmp_dir = os.environ.get("TMPDIR", tempfile.gettempdir())
    upload_dir = os.path.join(tmp_dir, "omnirag_uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename or "upload")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Ingest the saved file
    gate = get_gate()
    job = await gate.ingest(file_path, {})
    return job.to_dict()


@router.get("/intake", tags=["intake"])
async def list_intakes():
    """List all intake jobs."""
    gate = get_gate()
    return [job.to_dict() for job in gate.jobs.values()]


@router.get("/intake/{job_id}", tags=["intake"])
async def get_intake(job_id: str):
    """Get intake job details with documents and chunks."""
    gate = get_gate()
    job = gate.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    result = job.to_dict()
    docs = gate.get_documents(job_id)
    chunks = gate.get_chunks(job_id)

    result["documents"] = [d.to_dict() for d in docs[:50]]
    result["chunks_total"] = len(chunks)
    result["chunks_sample"] = [c.to_dict() for c in chunks[:20]]
    return result


@router.post("/intake/{job_id}/retry", tags=["intake"])
async def retry_intake(job_id: str):
    """Retry a failed or deferred job."""
    gate = get_gate()
    job = gate.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.state.value not in ("failed", "deferred"):
        raise HTTPException(400, f"Job is {job.state.value}, not retriable")

    new_job = await gate.ingest(job.source, job.config, job.pipeline)
    return new_job.to_dict()


# ─── Connectors ───

class ConnectorBody(BaseModel):
    source_type: str
    tenant_id: str = "default"
    auth_ref: str | None = None
    rate_limits: dict = {}
    backpressure: dict = {}


@router.post("/connectors", tags=["connectors"])
async def create_connector(body: ConnectorBody):
    """Register a new connector."""
    from omnirag.intake.models import RateLimits, BackpressureConfig, BackpressureMode
    config = ConnectorConfig(
        source_type=body.source_type,
        tenant_id=body.tenant_id,
        auth_ref=body.auth_ref,
    )
    if body.rate_limits:
        config.rate_limits = RateLimits(**body.rate_limits)
    if body.backpressure:
        bp = body.backpressure.copy()
        if "mode" in bp:
            bp["mode"] = BackpressureMode(bp["mode"])
        config.backpressure = BackpressureConfig(**bp)

    get_gate().register_connector(config)
    return config.to_dict()


@router.get("/connectors", tags=["connectors"])
async def list_connectors():
    """List registered connectors."""
    from omnirag.intake.connectors.registry import get_registry
    gate = get_gate()
    return {
        "available": get_registry().list(),
        "configured": [c.to_dict() for c in gate._connectors.values()],
    }


@router.post("/connectors/{connector_id}/sync", tags=["connectors"])
async def trigger_sync(connector_id: str, source: str = "", config: dict = {}):
    """Trigger manual sync for a connector."""
    if not source:
        raise HTTPException(400, "source is required")
    gate = get_gate()
    job = await gate.ingest(source, config)
    return job.to_dict()


# ─── Backpressure ───

@router.get("/backpressure/health", tags=["backpressure"])
async def backpressure_health():
    """Current indexer health status."""
    return {
        "indexers": get_backpressure_registry().get_all(),
        "all_healthy": get_backpressure_registry().is_healthy(),
        "blocked": get_backpressure_registry().get_blocked_indexers(),
    }


@router.get("/backpressure/admission", tags=["backpressure"])
async def admission_status():
    """Admission controller status."""
    return get_admission_controller().to_dict()


@router.get("/backpressure/circuit-breakers", tags=["backpressure"])
async def circuit_breakers():
    """Circuit breaker states."""
    return {
        "breakers": get_circuit_manager().get_all(),
        "open": get_circuit_manager().get_open(),
    }


@router.post("/backpressure/circuit-breakers/{indexer_id}/reset", tags=["backpressure"])
async def reset_circuit_breaker(indexer_id: str):
    """Reset a circuit breaker."""
    ok = get_circuit_manager().reset(indexer_id)
    if not ok:
        raise HTTPException(404, f"Circuit breaker '{indexer_id}' not found")
    return {"reset": True, "indexer_id": indexer_id}


# ─── Dead Letters ───

@router.get("/dead-letters", tags=["dead-letters"])
async def list_dead_letters():
    """List dead-lettered jobs."""
    return {
        "count": get_dead_letter_queue().count(),
        "letters": get_dead_letter_queue().list(),
    }


@router.post("/dead-letters/{letter_id}/replay", tags=["dead-letters"])
async def replay_dead_letter(letter_id: str):
    """Replay a dead-lettered job."""
    letter = get_dead_letter_queue().replay(letter_id)
    if not letter:
        raise HTTPException(404, f"Dead letter '{letter_id}' not found")
    gate = get_gate()
    source = letter.payload.get("source", "")
    config = letter.payload.get("config", {})
    if not source:
        raise HTTPException(400, "Dead letter has no source to replay")
    job = await gate.ingest(source, config)
    return {"replayed": True, "new_job": job.to_dict()}


# ─── Lineage ───

@router.get("/lineage", tags=["lineage"])
async def list_lineage(job_id: str | None = None, limit: int = 100):
    """Get lineage events."""
    store = get_lineage_store()
    return {
        "events": store.get_events(job_id, limit),
        "tombstones": store.get_tombstones(),
        "counts": store.count(),
    }


# ─── Cursors ───

@router.get("/cursors", tags=["cursors"])
async def list_cursors():
    """List all connector cursors."""
    return get_cursor_store().list()
