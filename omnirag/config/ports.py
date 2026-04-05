"""OmniRAG Port Registry — centralized port management.

All services in the 8100–8199 range. Every port is configurable via env var.
See docs/PORT-REGISTRY.md for the official specification.
"""

from __future__ import annotations

import os


def _port(env_var: str, default: int) -> int:
    return int(os.environ.get(env_var, str(default)))


def _url(env_var: str, default: str) -> str:
    return os.environ.get(env_var, default)


# ─── Core Application ───
OMNIRAG_API_PORT = _port("OMNIRAG_API_PORT", 8100)
OMNIRAG_WORKER_PORT = _port("OMNIRAG_WORKER_PORT", 8101)
OMNIRAG_EMBED_PORT = _port("OMNIRAG_EMBED_PORT", 8102)
OMNIRAG_WEBHOOK_PORT = _port("OMNIRAG_WEBHOOK_PORT", 8103)
OMNIRAG_METRICS_PORT = _port("OMNIRAG_METRICS_PORT", 8104)

# ─── Graph Store (Neo4j) ───
NEO4J_BOLT_PORT = _port("NEO4J_BOLT_PORT", 8110)
NEO4J_HTTP_PORT = _port("NEO4J_HTTP_PORT", 8111)
NEO4J_URI = _url("NEO4J_URI", f"bolt://localhost:{NEO4J_BOLT_PORT}")
NEO4J_USER = _url("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = _url("NEO4J_PASSWORD", "omnirag")

# ─── Vector Store (Qdrant) ───
QDRANT_PORT = _port("QDRANT_PORT", 8120)
QDRANT_HOST = _url("QDRANT_HOST", "localhost")
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

# ─── Keyword Index (Elasticsearch) ───
ELASTICSEARCH_PORT = _port("ELASTICSEARCH_PORT", 8130)
ELASTICSEARCH_URL = _url("ELASTICSEARCH_URL", f"http://localhost:{ELASTICSEARCH_PORT}")

# ─── Cache + Consistency (Redis) ───
REDIS_PORT = _port("REDIS_PORT", 8140)
REDIS_ADDR = _url("REDIS_ADDR", f"localhost:{REDIS_PORT}")
REDIS_URL = _url("REDIS_URL", f"redis://localhost:{REDIS_PORT}/0")

# ─── Local LLM (Ollama) ───
OLLAMA_PORT = _port("OLLAMA_PORT", 8150)
OLLAMA_HOST = _url("OLLAMA_HOST", f"http://localhost:{OLLAMA_PORT}")
OLLAMA_MODEL = _url("OLLAMA_MODEL", "llama3")

# ─── Control Plane DB (PostgreSQL) ───
POSTGRES_PORT = _port("POSTGRES_PORT", 8160)
DATABASE_URL = _url("DATABASE_URL", f"postgresql://omnirag:omnirag@localhost:{POSTGRES_PORT}/omnirag")


def get_all() -> dict:
    """Return all port assignments for display/diagnostics."""
    return {
        "omnirag_api": OMNIRAG_API_PORT,
        "omnirag_worker": OMNIRAG_WORKER_PORT,
        "omnirag_embed": OMNIRAG_EMBED_PORT,
        "omnirag_webhook": OMNIRAG_WEBHOOK_PORT,
        "omnirag_metrics": OMNIRAG_METRICS_PORT,
        "neo4j_bolt": NEO4J_BOLT_PORT,
        "neo4j_http": NEO4J_HTTP_PORT,
        "qdrant": QDRANT_PORT,
        "elasticsearch": ELASTICSEARCH_PORT,
        "redis": REDIS_PORT,
        "ollama": OLLAMA_PORT,
        "postgres": POSTGRES_PORT,
    }
