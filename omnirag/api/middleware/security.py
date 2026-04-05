"""Security middleware — JWT extraction, rate limiting, request state injection.

Plugs auth.py and rate_limiter.py into FastAPI's request lifecycle.
"""

from __future__ import annotations

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from omnirag.output.auth import validate_jwt, get_default_identity, UserIdentity
from omnirag.output.rate_limiter import get_rate_limiter
from omnirag.output.metrics import get_output_metrics

# Endpoints that skip auth
PUBLIC_PATHS = {"/", "/health", "/metrics", "/ready", "/docs", "/redoc", "/openapi.json", "/static"}
# Endpoints that require specific scopes
SCOPE_MAP = {
    "/v1/search": "rag:search",
    "/v1/stream": "rag:search",
    "/v1/export": "rag:export",
    "/v1/webhooks": "rag:admin",
    "/v1/search/debug": "rag:admin",
}
# Rate-limited endpoints
RATE_LIMIT_MAP = {
    "/v1/search": "search",
    "/v1/search/debug": "search",
    "/v1/export": "export",
}

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Injects user identity and enforces auth + rate limits on every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        metrics = get_output_metrics()

        # Skip auth for public paths and static files
        if any(path.startswith(p) for p in PUBLIC_PATHS) or path.startswith("/static"):
            request.state.user_principals = ["public"]
            request.state.user_hash = "anonymous"
            request.state.identity = get_default_identity()
            return await call_next(request)

        # ── JWT Authentication ──
        identity: UserIdentity
        if AUTH_ENABLED:
            auth_header = request.headers.get("authorization", "")
            token = ""
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif request.query_params.get("token"):
                token = request.query_params["token"]

            if not token:
                return JSONResponse(status_code=401, content={"error": "Missing authentication token"})

            identity_or_none = validate_jwt(token)
            if identity_or_none is None:
                return JSONResponse(status_code=401, content={"error": "Invalid or expired token"})
            identity = identity_or_none
        else:
            identity = get_default_identity()

        # Inject into request state
        request.state.identity = identity
        request.state.user_principals = identity.user_principals
        request.state.user_hash = identity.user_hash

        # ── Scope Check ──
        for prefix, required_scope in SCOPE_MAP.items():
            if path.startswith(prefix):
                if not identity.has_scope(required_scope):
                    return JSONResponse(
                        status_code=403,
                        content={"error": f"Missing scope: {required_scope}"},
                    )
                break

        # ── Rate Limiting ──
        limiter = get_rate_limiter()
        rate_headers: dict[str, str] = {}

        for prefix, endpoint_name in RATE_LIMIT_MAP.items():
            if path.startswith(prefix):
                result = limiter.check(identity.principal, endpoint_name)
                rate_headers = limiter.headers(result)

                if not result.allowed:
                    metrics.rate_limit_hits.inc(endpoint_name)
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Rate limit exceeded", "retry_after": result.retry_after},
                        headers=rate_headers,
                    )
                break

        # ── Execute request ──
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        # Track metrics for search endpoints
        if path.startswith("/v1/search"):
            metrics.query_latency.observe(elapsed)

        # Add rate limit headers
        for k, v in rate_headers.items():
            response.headers[k] = v

        return response
