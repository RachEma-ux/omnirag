"""Consistency coordinator — Redis index versioning + polling for read-after-write.

Keys:
  global:index_version — monotonic counter
  store:vector:version, store:keyword:version, store:metadata:version
  user:{hash}:last_version — per-user tracking

Polling: 50ms interval, 500ms max wait.
Timeout → X-Consistency: eventual.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

WAIT_MAX_MS = 500
POLL_INTERVAL_MS = 50


class ConsistencyCoordinator:
    """Ensures read-after-write consistency across 3 index stores."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._use_fallback = True
        # In-memory fallback
        self._versions = {
            "global": 0,
            "vector": 0,
            "keyword": 0,
            "metadata": 0,
        }
        self._user_versions: dict[str, int] = {}

    def _try_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import os
            import redis
            addr = os.environ.get("REDIS_ADDR", "localhost:6379")
            host, port = addr.rsplit(":", 1)
            self._redis = redis.Redis(host=host, port=int(port), decode_responses=True)
            self._redis.ping()
            self._use_fallback = False
            return self._redis
        except Exception:
            self._use_fallback = True
            return None

    def commit_batch(self, stores_written: list[str]) -> int:
        """Called after writing a batch to all stores. Returns new version."""
        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                new_version = r.incr("global:index_version")
                for store in stores_written:
                    r.set(f"store:{store}:version", new_version)
                return new_version
            except Exception:
                pass

        # Fallback
        self._versions["global"] += 1
        v = self._versions["global"]
        for store in stores_written:
            self._versions[store] = v
        return v

    def set_user_version(self, user_hash: str, version: int) -> None:
        """Track user's last observed version."""
        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                r.set(f"user:{user_hash}:last_version", version)
                return
            except Exception:
                pass
        self._user_versions[user_hash] = version

    def get_user_version(self, user_hash: str) -> int:
        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                v = r.get(f"user:{user_hash}:last_version")
                return int(v) if v else 0
            except Exception:
                pass
        return self._user_versions.get(user_hash, 0)

    def _min_store_version(self) -> int:
        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                versions = []
                for store in ("vector", "keyword", "metadata"):
                    v = r.get(f"store:{store}:version")
                    versions.append(int(v) if v else 0)
                return min(versions) if versions else 0
            except Exception:
                pass
        return min(self._versions.get("vector", 0), self._versions.get("keyword", 0), self._versions.get("metadata", 0))

    async def wait_for_consistency(self, user_version: int, timeout_ms: int = WAIT_MAX_MS) -> str:
        """Poll until all stores catch up to user's version. Returns 'strong' or 'eventual'."""
        if user_version <= 0:
            return "strong"

        start = time.monotonic()
        deadline = start + (timeout_ms / 1000)

        while time.monotonic() < deadline:
            min_version = self._min_store_version()
            if user_version <= min_version:
                return "strong"
            await asyncio.sleep(POLL_INTERVAL_MS / 1000)

        logger.warning("consistency.timeout", user_version=user_version, min_store=self._min_store_version())
        return "eventual"

    def current_version(self) -> dict:
        return {
            "global": self._versions["global"],
            "vector": self._versions.get("vector", 0),
            "keyword": self._versions.get("keyword", 0),
            "metadata": self._versions.get("metadata", 0),
            "mode": "redis" if not self._use_fallback else "in-memory",
        }


_coordinator = ConsistencyCoordinator()


def get_consistency_coordinator() -> ConsistencyCoordinator:
    return _coordinator
