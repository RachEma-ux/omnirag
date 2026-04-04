"""API middleware — authentication, rate limiting, request logging."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

import structlog

from omnirag.observability.metrics import metrics

logger = structlog.get_logger()

# API key auth (optional — disabled if OMNIRAG_API_KEYS is not set)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_allowed_keys: set[str] | None = None


def _load_keys() -> set[str] | None:
    """Load allowed API keys from environment."""
    global _allowed_keys
    keys_str = os.environ.get("OMNIRAG_API_KEYS", "")
    if keys_str:
        _allowed_keys = set(keys_str.split(","))
    return _allowed_keys


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Verify API key if authentication is enabled."""
    keys = _load_keys()
    if keys is None:
        return None  # Auth disabled

    if api_key is None or api_key not in keys:
        raise HTTPException(
            status_code=401, detail="Invalid or missing API key"
        )
    return api_key


# Simple in-memory rate limiter
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60  # seconds
_RATE_MAX = int(os.environ.get("OMNIRAG_RATE_LIMIT", "100"))


def check_rate_limit(client_ip: str) -> None:
    """Check if client has exceeded rate limit."""
    now = time.time()
    window_start = now - _RATE_WINDOW

    # Clean old entries
    _rate_limits[client_ip] = [
        t for t in _rate_limits[client_ip] if t > window_start
    ]

    if len(_rate_limits[client_ip]) >= _RATE_MAX:
        metrics.inc("omnirag_rate_limited_total", client=client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({_RATE_MAX}/min)",
        )

    _rate_limits[client_ip].append(now)


async def log_request(request: Request) -> None:
    """Log incoming request and record metrics."""
    metrics.inc("omnirag_requests_total", method=request.method, path=request.url.path)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )
