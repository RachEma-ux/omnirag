"""Rate limiter — sliding window (in-memory, Redis-ready interface)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class RateLimitConfig:
    search_per_minute: int = 100
    export_per_hour: int = 10
    websocket_max_concurrent: int = 10


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: int | None = None


class SlidingWindowLimiter:
    """Per-user sliding window rate limiter."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._overrides: set[str] = set()

    def override(self, principal: str) -> None:
        """Temporarily bypass rate limit for a principal."""
        self._overrides.add(principal)

    def remove_override(self, principal: str) -> None:
        self._overrides.discard(principal)

    def check(self, principal: str, endpoint: str) -> RateLimitResult:
        """Check if request is allowed."""
        if principal in self._overrides:
            return RateLimitResult(allowed=True, limit=999999, remaining=999999, reset_at=0)

        now = time.time()
        key = f"{principal}:{endpoint}"

        if endpoint == "search":
            window = 60
            limit = self.config.search_per_minute
        elif endpoint == "export":
            window = 3600
            limit = self.config.export_per_hour
        else:
            window = 60
            limit = self.config.search_per_minute

        # Clean old entries
        timestamps = self._windows[key]
        cutoff = now - window
        self._windows[key] = [t for t in timestamps if t > cutoff]
        timestamps = self._windows[key]

        remaining = limit - len(timestamps)
        reset_at = (timestamps[0] + window) if timestamps else (now + window)

        if remaining <= 0:
            return RateLimitResult(
                allowed=False, limit=limit, remaining=0,
                reset_at=reset_at, retry_after=int(reset_at - now) + 1,
            )

        # Allow and record
        self._windows[key].append(now)
        return RateLimitResult(
            allowed=True, limit=limit, remaining=remaining - 1, reset_at=reset_at,
        )

    def headers(self, result: RateLimitResult) -> dict[str, str]:
        """Generate X-RateLimit-* response headers."""
        h = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_at)),
        }
        if result.retry_after is not None:
            h["Retry-After"] = str(result.retry_after)
        return h


_limiter = SlidingWindowLimiter()


def get_rate_limiter() -> SlidingWindowLimiter:
    return _limiter
