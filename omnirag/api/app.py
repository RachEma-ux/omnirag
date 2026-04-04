"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from omnirag import __version__
from omnirag.api.routes.health import router as health_router
from omnirag.api.routes.invoke import router as invoke_router
from omnirag.api.routes.pipelines import router as pipelines_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OmniRAG",
        description="Open-source control plane for RAG systems",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(health_router, tags=["health"])
    app.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
    app.include_router(invoke_router, tags=["invoke"])

    return app
