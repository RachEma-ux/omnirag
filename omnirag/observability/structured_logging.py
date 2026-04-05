"""Structured JSON logging — query logs with all required fields."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict


@dataclass
class QueryLogEntry:
    """Structured log entry for every query (JSON lines format)."""
    timestamp: str = ""
    request_id: str = ""
    user_principal_hash: str = ""
    query: str = ""
    mode: str = ""
    route_decision: str = ""
    cache_hit: bool = False
    latency_ms: float = 0
    retrieval_latency_ms: float = 0
    generation_latency_ms: float = 0
    fallback_used: bool = False
    rate_limit_remaining: int = -1
    status_code: int = 200
    error: str | None = None

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = d["timestamp"] or time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if d["error"] is None:
            del d["error"]
        return json.dumps(d)

    @staticmethod
    def hash_principal(principal: str) -> str:
        return f"sha256:{hashlib.sha256(principal.encode()).hexdigest()[:16]}"


_log_buffer: list[QueryLogEntry] = []


def log_query(entry: QueryLogEntry) -> None:
    """Append query log entry to buffer."""
    _log_buffer.append(entry)


def get_recent_logs(limit: int = 50) -> list[dict]:
    return [json.loads(e.to_json()) for e in _log_buffer[-limit:]]


def get_log_count() -> int:
    return len(_log_buffer)
