"""Per-connector token bucket (leaky bucket) rate limiter."""

from __future__ import annotations

import time


class TokenBucket:
    """Rate limiter using leaky bucket algorithm.

    Bucket size = docs_per_minute / 10 (burst allowance).
    Rate = docs_per_minute / 60 per second.
    """

    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self.rate = rate_per_second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    @classmethod
    def from_docs_per_minute(cls, docs_per_minute: int) -> TokenBucket:
        rate = docs_per_minute / 60.0
        capacity = max(1, docs_per_minute // 10)
        return cls(rate, capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def available(self) -> float:
        self._refill()
        return self.tokens

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
