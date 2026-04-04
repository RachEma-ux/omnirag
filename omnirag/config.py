"""OmniRAG configuration — environment-based settings.

All config is loaded from environment variables with sensible defaults.
Production deployments should set these via K8s secrets / .env files.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """API server configuration."""
    host: str = "127.0.0.1"
    port: int = 8100
    workers: int = 1
    reload: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class SecurityConfig(BaseModel):
    """Authentication and rate limiting."""
    api_keys: list[str] = Field(default_factory=list)
    rate_limit: int = 100  # requests per minute
    enabled: bool = False


class CompilerConfig(BaseModel):
    """Selective Execution Planner settings."""
    enabled: bool = True
    cache_dir: str = "~/.omnirag/compiled_cache"
    auto_compile: bool = True


class ObservabilityConfig(BaseModel):
    """Metrics, tracing, logging."""
    log_level: str = "INFO"
    log_format: str = "json"
    otel_enabled: bool = False
    otel_endpoint: str = ""
    prometheus_enabled: bool = True


class OmniRAGConfig(BaseModel):
    """Root configuration."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    compiler: CompilerConfig = Field(default_factory=CompilerConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)


def load_config() -> OmniRAGConfig:
    """Load configuration from environment variables."""
    api_keys_str = os.environ.get("OMNIRAG_API_KEYS", "")
    api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

    return OmniRAGConfig(
        server=ServerConfig(
            host=os.environ.get("OMNIRAG_HOST", "127.0.0.1"),
            port=int(os.environ.get("OMNIRAG_PORT", "8100")),
            workers=int(os.environ.get("OMNIRAG_WORKERS", "1")),
        ),
        security=SecurityConfig(
            api_keys=api_keys,
            rate_limit=int(os.environ.get("OMNIRAG_RATE_LIMIT", "100")),
            enabled=bool(api_keys),
        ),
        compiler=CompilerConfig(
            enabled=os.environ.get("OMNIRAG_COMPILER", "true").lower() == "true",
        ),
        observability=ObservabilityConfig(
            log_level=os.environ.get("OMNIRAG_LOG_LEVEL", "INFO"),
            otel_enabled=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "") != "",
            otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
        ),
    )


# Global singleton
config = load_config()
