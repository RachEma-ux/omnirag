"""GraphRAG caching — Redis with mode-specific TTL and invalidation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import structlog

from omnirag.graphrag.models import GraphEvidenceBundle, QueryMode

logger = structlog.get_logger(__name__)

TTL_BASIC = 900     # 15 minutes
TTL_LOCAL = 600     # 10 minutes
TTL_GLOBAL = 3600   # 1 hour
TTL_DRIFT = 300     # 5 minutes
TTL_HYBRID = 600    # 10 minutes


def _hash(text: str) -> str:
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


def _user_hash(principals: list[str]) -> str:
    return _hash(":".join(sorted(principals)))


class GraphCache:
    """Redis-backed cache for GraphRAG query results."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._use_fallback = True
        self._memory: dict[str, tuple[str, float]] = {}  # key → (json, expires_at)
        self.stats = {"hits": 0, "misses": 0, "writes": 0, "invalidations": 0}

    def _try_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis
            from omnirag.config.ports import REDIS_ADDR as _REDIS_DEFAULT
            addr = os.environ.get("REDIS_ADDR", _REDIS_DEFAULT)
            host, port = addr.rsplit(":", 1)
            self._redis = redis.Redis(host=host, port=int(port), decode_responses=True)
            self._redis.ping()
            self._use_fallback = False
            return self._redis
        except Exception:
            self._use_fallback = True
            return None

    def _key(self, mode: QueryMode, query: str, principals: list[str],
             entity_ids: list[str] | None = None,
             graph_version: int = 0, embedding_version: int = 0,
             prompt_version: int = 0) -> str:
        """Build cache key: {mode}:{query_hash}:{acl_fingerprint}:{graph_version}:{embed_version}:{prompt_version}"""
        user = _user_hash(principals)
        query_h = _hash(query)
        base = f"graphrag:{mode.value}:{query_h}:{user}:{graph_version}:{embedding_version}:{prompt_version}"
        if mode == QueryMode.DRIFT and entity_ids:
            entity_h = _hash(":".join(sorted(entity_ids)))
            base += f":{entity_h}"
        return base

    def _ttl(self, mode: QueryMode) -> int:
        return {
            QueryMode.BASIC: TTL_BASIC,
            QueryMode.LOCAL: TTL_LOCAL,
            QueryMode.GLOBAL: TTL_GLOBAL,
            QueryMode.DRIFT: TTL_DRIFT,
            QueryMode.HYBRID: TTL_HYBRID,
        }.get(mode, TTL_LOCAL)

    def get(self, mode: QueryMode, query: str, principals: list[str],
            entity_ids: list[str] | None = None) -> GraphEvidenceBundle | None:
        """Check cache. Returns cached bundle or None."""
        key = self._key(mode, query, principals, entity_ids)
        r = self._try_redis()

        if r and not self._use_fallback:
            try:
                data = r.get(key)
                if data:
                    self.stats["hits"] += 1
                    bundle_dict = json.loads(data)
                    return self._dict_to_bundle(bundle_dict)
            except Exception:
                pass

        # Memory fallback
        entry = self._memory.get(key)
        if entry:
            data_str, expires = entry
            if time.time() < expires:
                self.stats["hits"] += 1
                return self._dict_to_bundle(json.loads(data_str))
            else:
                del self._memory[key]

        self.stats["misses"] += 1
        return None

    def put(self, mode: QueryMode, query: str, principals: list[str],
            bundle: GraphEvidenceBundle, entity_ids: list[str] | None = None) -> None:
        """Cache a result."""
        key = self._key(mode, query, principals, entity_ids)
        ttl = self._ttl(mode)
        data = json.dumps(bundle.to_dict())

        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                r.setex(key, ttl, data)
                self.stats["writes"] += 1
                return
            except Exception:
                pass

        self._memory[key] = (data, time.time() + ttl)
        self.stats["writes"] += 1

    def invalidate_global(self) -> int:
        """Invalidate all global cache entries (on community report change)."""
        count = 0
        r = self._try_redis()
        if r and not self._use_fallback:
            try:
                keys = r.keys("graphrag:global:*")
                if keys:
                    count = r.delete(*keys)
            except Exception:
                pass
        else:
            to_delete = [k for k in self._memory if k.startswith("graphrag:global:")]
            for k in to_delete:
                del self._memory[k]
            count = len(to_delete)

        self.stats["invalidations"] += count
        return count

    def _dict_to_bundle(self, d: dict) -> GraphEvidenceBundle:
        return GraphEvidenceBundle(
            mode=QueryMode(d.get("mode", "basic")),
            confidence=d.get("confidence", 0),
            coverage=d.get("coverage", 0),
            cache_hit=True,
        )

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "mode": "redis" if not self._use_fallback else "in-memory",
            "memory_entries": len(self._memory),
        }


_cache = GraphCache()


def get_graph_cache() -> GraphCache:
    return _cache
