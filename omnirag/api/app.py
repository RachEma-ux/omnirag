"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from omnirag import __version__
from omnirag.api.routes.health import router as health_router
from omnirag.api.routes.invoke import router as invoke_router
from omnirag.api.routes.pipelines import router as pipelines_router
from omnirag.api.routes.tasks import router as tasks_router
from omnirag.observability.metrics import metrics


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OmniRAG",
        description="Open-source control plane for RAG systems",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router, tags=["health"])
    app.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
    app.include_router(invoke_router, tags=["invoke"])
    app.include_router(tasks_router, tags=["tasks"])

    # Prometheus metrics endpoint
    @app.get("/metrics", response_class=PlainTextResponse, tags=["observability"])
    async def prometheus_metrics() -> str:
        return metrics.export_prometheus()

    # Register default adapters on startup
    @app.on_event("startup")
    async def startup() -> None:
        from omnirag.adapters.defaults import register_defaults
        register_defaults()

    return app
