# OmniRAG Port Registry — Official Service Port Management

**Version:** 1.0
**Status:** Mandatory
**Effective:** 2026-04-05

---

## Purpose

This document defines the official port assignment policy for the OmniRAG platform. All OmniRAG services operate within a **contiguous reserved block: ports 8100–8199**. This prevents collisions with other local services, simplifies firewall rules, and provides a predictable, memorable port scheme.

---

## Port Assignment Table

### Core Application (8100–8109)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8100** | OmniRAG API | HTTP | Main FastAPI server — intake, search, OmniGraph, UI shell |
| **8101** | OmniGraph Worker | HTTP | Background: entity extraction, communities, reports |
| **8102** | Embedding Worker | HTTP | Background: async embedding pipeline |
| **8103** | Webhook Dispatcher | HTTP | Outbound webhook delivery service |
| **8104** | Metrics Exporter | HTTP | Prometheus `/metrics` endpoint |
| 8105–8109 | *Reserved* | — | Future application services |

### Graph Store — Neo4j (8110–8119)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8110** | Neo4j Bolt | Bolt | Cypher query protocol (remapped from 7687) |
| **8111** | Neo4j HTTP | HTTP | Neo4j Browser UI (remapped from 7474) |
| 8112–8119 | *Reserved* | — | Neo4j clustering, GDS |

### Vector Store — Qdrant (8120–8129)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8120** | Qdrant HTTP | HTTP | REST API (remapped from 6333) |
| **8121** | Qdrant gRPC | gRPC | High-performance API (remapped from 6334) |
| 8122–8129 | *Reserved* | — | Qdrant clustering |

### Keyword Index — Elasticsearch (8130–8139)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8130** | Elasticsearch | HTTP | REST API (remapped from 9200) |
| 8131–8139 | *Reserved* | — | ES clustering, Kibana |

### Cache — Redis (8140–8149)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8140** | Redis | TCP | Cache + consistency coordinator (remapped from 6379) |
| 8141–8149 | *Reserved* | — | Redis Sentinel, Redis Cluster |

### Local LLM — Ollama (8150–8159)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8150** | Ollama | HTTP | LLM API (remapped from 11434) |
| 8151–8159 | *Reserved* | — | Additional model servers |

### Control Plane DB — PostgreSQL (8160–8169)

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| **8160** | PostgreSQL | TCP | Control plane database (remapped from 5432) |
| 8161–8169 | *Reserved* | — | Read replicas, pgBouncer |

### Reserved for Future (8170–8199)

| Range | Purpose |
|-------|---------|
| 8170–8179 | Message queue (Kafka, RabbitMQ) |
| 8180–8189 | Monitoring (Grafana, Jaeger) |
| 8190–8199 | Future expansion |

---

## Configuration

### Environment Variables

All ports are configurable via environment variables. The centralized config module is at `omnirag/config/ports.py`.

```bash
# Core
OMNIRAG_API_PORT=8100

# Backing services
NEO4J_BOLT_PORT=8110
NEO4J_HTTP_PORT=8111
QDRANT_PORT=8120
ELASTICSEARCH_PORT=8130
REDIS_PORT=8140
OLLAMA_PORT=8150
POSTGRES_PORT=8160

# Connection strings (derived from ports)
DATABASE_URL=postgresql://omnirag:omnirag@localhost:8160/omnirag
NEO4J_URI=bolt://localhost:8110
REDIS_URL=redis://localhost:8140/0
ELASTICSEARCH_URL=http://localhost:8130
OLLAMA_HOST=http://localhost:8150
```

### .env File

Copy `docker/.env.example` to `docker/.env` and adjust if needed:

```bash
cp docker/.env.example docker/.env
```

### Docker Compose

All services in `docker/docker-compose.full.yml` use the port variables:

```yaml
# Example: PostgreSQL mapped from container 5432 to host 8160
postgres:
  ports:
    - "${POSTGRES_PORT:-8160}:5432"
```

---

## Implementation

### Python Config Module

```python
from omnirag.config.ports import (
    OMNIRAG_API_PORT,    # 8100
    NEO4J_URI,           # bolt://localhost:8110
    QDRANT_HOST,         # localhost
    QDRANT_PORT,         # 8120
    ELASTICSEARCH_URL,   # http://localhost:8130
    REDIS_ADDR,          # localhost:8140
    OLLAMA_HOST,         # http://localhost:8150
    DATABASE_URL,        # postgresql://...localhost:8160/omnirag
)
```

All service modules import from `omnirag.config.ports` instead of hardcoding ports. Environment variables always take precedence over defaults.

### API Endpoint

```
GET /ports → returns all port assignments
```

```json
{
  "ports": {
    "omnirag_api": 8100,
    "neo4j_bolt": 8110,
    "qdrant": 8120,
    "elasticsearch": 8130,
    "redis": 8140,
    "ollama": 8150,
    "postgres": 8160
  },
  "range": "8100-8199"
}
```

---

## Rules

1. **All OmniRAG services MUST use ports in the 8100–8199 range.** No exceptions.
2. **No hardcoded ports in application code.** All port references MUST go through `omnirag.config.ports`.
3. **Environment variables always override defaults.** The `.env` file is the single source of truth for deployment-specific values.
4. **Container internal ports stay default.** Only the host-mapped port changes. Example: PostgreSQL runs on 5432 inside the container, mapped to 8160 on the host.
5. **Reserved ranges MUST NOT be used** until officially assigned in this document.
6. **Port changes require updating this document** before implementation.

---

## Collision Avoidance

| External Service | Default Port | OmniRAG Port | Conflict? |
|-----------------|-------------|-------------|-----------|
| MyNewAp1Claude | 3000 | — | No |
| OpenCode | 4096 | — | No |
| System PostgreSQL | 5432 | 8160 | No |
| System Redis | 6379 | 8140 | No |
| Default Neo4j | 7687 | 8110 | No |
| Default Qdrant | 6333 | 8120 | No |
| Default ES | 9200 | 8130 | No |
| Default Ollama | 11434 | 8150 | No |

The 8100–8199 range does not conflict with any commonly used service port.

---

## Quick Reference

```
8100  OmniRAG API          ← your main entry point
8110  Neo4j (graph)
8120  Qdrant (vectors)
8130  Elasticsearch (text)
8140  Redis (cache)
8150  Ollama (LLM)
8160  PostgreSQL (data)
```

Mnemonic: **81** = OmniRAG, last two digits = service type (00=app, 10=graph, 20=vector, 30=text, 40=cache, 50=llm, 60=db).
