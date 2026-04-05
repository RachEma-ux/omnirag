"""Health and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from omnirag import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@router.get("/ports")
async def ports() -> dict:
    """Port registry — all service port assignments."""
    from omnirag.config.ports import get_all
    return {"ports": get_all(), "range": "8100-8199"}


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    """Basic metrics endpoint (Prometheus integration planned)."""
    return {
        "version": __version__,
        "pipelines_loaded": 0,
        "total_invocations": 0,
    }
