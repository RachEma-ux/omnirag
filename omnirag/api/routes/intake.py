"""Intake Gate API — universal ingest endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from omnirag.intake.gate import get_gate
from omnirag.intake.models import IntakeRequest

router = APIRouter()


class IntakeBody(BaseModel):
    """Request body for intake."""

    source: str
    config: dict = {}
    pipeline: str | None = None
    options: dict = {}

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "/path/to/documents/*.pdf",
                    "config": {"recursive": True, "max_files": 100},
                    "pipeline": "pdf_qa",
                    "options": {"chunk_size": 512},
                },
                {
                    "source": "https://example.com/report.pdf",
                    "config": {},
                },
                {
                    "source": "s3://my-bucket/docs/",
                    "config": {
                        "credentials": {
                            "aws_access_key": "...",
                            "aws_secret_key": "...",
                        }
                    },
                },
                {
                    "source": "github://owner/repo/docs",
                    "config": {"token": "ghp_...", "branch": "main"},
                },
            ]
        }
    }


@router.post("/intake")
async def create_intake(body: IntakeBody):
    """Ingest data from any source — files, URLs, S3, GitHub, databases, etc."""
    request = IntakeRequest(
        source=body.source,
        config=body.config,
        pipeline=body.pipeline,
        options=body.options,
    )
    gate = get_gate()
    job = await gate.ingest(request)
    return job.to_dict()


@router.get("/intake/{job_id}")
async def get_intake(job_id: str):
    """Get intake job status and results."""
    gate = get_gate()
    job = gate.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Intake job '{job_id}' not found")

    result = job.to_dict()
    if job.documents_created > 0:
        docs = gate.get_documents(job_id)
        result["documents"] = [
            {
                "id": d.id,
                "format": d.format,
                "source_uri": d.source_uri,
                "connector": d.connector,
                "loader": d.loader,
                "text_length": len(d.text),
                "text_preview": d.text[:200] + "..." if len(d.text) > 200 else d.text,
                "metadata": d.metadata,
            }
            for d in docs[:50]  # limit preview to 50 docs
        ]
    return result


@router.get("/intake")
async def list_intakes():
    """List all intake jobs."""
    gate = get_gate()
    return [job.to_dict() for job in gate.jobs.values()]
