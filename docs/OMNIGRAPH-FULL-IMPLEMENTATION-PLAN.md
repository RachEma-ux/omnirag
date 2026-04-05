# OmniGraph Full Implementation Plan — Nothing Skipped

**Date:** 2026-04-05
**Input:** 6 OmniGraph spec files (Engineering Spec, Tech Spec, Roadmap, Artifacts, README, Downloadable Files)
**Policy:** Full implementation. Every feature, every service, every component. No deferrals.
**Target:** Upgrade OmniRAG into the complete Universal GraphRAG Platform as specified.

---

## Everything That Must Be Built

### From the 14 Mandatory Features

| # | Feature | Status | Plan Phase |
|---|---------|--------|-----------|
| 1 | LLM entity extraction | Partial (regex only) | G3 |
| 2 | LLM relationship extraction | Partial (co-occurrence only) | G3 |
| 3 | Entity resolution (HDBSCAN + LLM verify) | Partial (no LLM verify) | G4 |
| 4 | Hierarchical Leiden communities | Partial (single resolution) | G5 |
| 5 | LLM community reports | Done (3-tier) | G9 (enrich) |
| 6 | 5 query modes | Done | G6 (upgrade context) |
| 7 | 3-stage query router | Done | G8 (expand rules + override) |
| 8 | Graph-aware context building | Missing | G6 |
| 9 | Multi-store (Neo4j, NetworkX, PostgreSQL+pgvector) | Partial | G10 + G13 |
| 10 | ACL per node | Done | G9 (ACL fingerprint in cache) |
| 11 | Mode-specific caching | Done | G9 (upgrade keys) |
| 12 | Observability (8 metrics) | Partial | G7 + G12 |
| 13 | Graph Explorer UI | Partial (basic) | G15 |
| 14 | 4 extraction modes (Regex/LLM/Schema/Hybrid) | Partial (regex only) | G3 + G11 |

### From the 12 Services + Cross-Cutting

| # | Service | Status | Plan Phase |
|---|---------|--------|-----------|
| 1 | Ingestion Service | Done (12-state gate) | Keep |
| 2 | Extraction Service | Partial | G3 |
| 3 | Entity Resolution Service | Partial | G4 |
| 4 | Graph Build Service | Partial | G10 |
| 5 | Graph Intelligence Service | Partial | G5 |
| 6 | Community Report Service | Done | G9 (enrich) |
| 7 | Query Router | Done | G8 (expand) |
| 8 | Retrieval Service | Done | G6 (context) |
| 9 | Context Builder | Missing | G6 |
| 10 | Authorization Engine | Done | Keep |
| 11 | Reasoning Service | Done | G7 (tracing) |
| 12 | Workflow Runtime (LangGraph + AutoGen) | Missing | G14 |
| — | Cache Manager | Done | G9 (upgrade) |
| — | Control Plane | Partial | G7 + G12 |
| — | API Layer | Done | G7 (traces API) |
| — | Next.js Frontend | Missing | G15 |
| — | Chainlit Ops UI | Missing | G16 |
| — | MCP Tool Protocol | Missing | G17 |

### From the Tech Stack

| Component | Status | Plan Phase |
|-----------|--------|-----------|
| Python 3.11+ FastAPI | Done | Keep |
| Neo4j 5+ (canonical graph) | Done (fallback mode) | G10 |
| NetworkX (in-memory workspace) | Done | Keep |
| PostgreSQL 15+ with pgvector + FTS | Partial (no pgvector) | G13 |
| Ollama (local LLM) | Done | Keep |
| Redis (cache) | Done | Keep |
| LlamaIndex Property Graph | Missing | G18 |
| MiniLM-L6 router classifier | Missing (training infra done) | G8 |
| MCP (Model Context Protocol) | Missing | G17 |
| OpenSPG / KAG (schema extraction) | Missing | G11 |
| LangGraph (workflows) | Missing | G14 |
| AutoGen (multi-agent) | Missing | G14 |
| Prometheus + OpenTelemetry + Grafana | Partial (Prometheus stubs) | G12 |
| Next.js (main UI) | Missing (have vanilla JS) | G15 |
| Chainlit (ops UI) | Missing | G16 |
| Power BI connector | Missing | G19 |
| Docker Compose (full stack) | Done | Keep + extend |

---

## Full Implementation Plan (19 Phases)

### Foundation (G1–G2)

#### Phase G1 — Canonical Data Model
**Files: ~2 | Lines: ~400**

New objects: `Extraction`, `ResolutionCase`, `QueryPlan`, `ContextBundle`, `Answer`, `AnswerTrace`, `CacheKey`, `MetricEvent`, `AgentRun`, `EvaluationResult`

Upgrade existing: add `description` to Entity/Relation, `provenance_span` to Extraction, `parent_community_id` to Community

#### Phase G2 — 23 Service Contracts
**Files: ~1 | Lines: ~300**

Define every interface as Python ABC: Parser, Normalizer, Extractor, EntityResolver, GraphBuilder, CommunityBuilder, ReportGenerator, Embedder, GraphStore, VectorStore, TextIndex, GraphAlgorithm, QueryRouter, RetrievalPlanner, GraphRetriever, VectorRetriever, HybridRetriever, ContextBuilder, AuthorizationEngine, CacheManager, Reasoner, AnswerSynthesizer, TraceRecorder

---

### Core Quality Upgrade (G3–G5)

#### Phase G3 — LLM-Powered Extraction (Features #1, #2, #14)
**Files: ~4 | Lines: ~600**

- `LLMEntityExtractor` with prompted extraction via Ollama/OpenAI
- `LLMRelationshipExtractor` with typed relationships + descriptions
- `prompts.py` with all prompt templates
- Extraction mode selector: regex / llm / schema / hybrid
- Per-source mode policies (JSON config)
- 3-tier fallback: LLM → spaCy → regex

#### Phase G4 — Entity Resolution Upgrade (Feature #3)
**Files: ~1 | Lines: ~200**

- Blocking step: exact name, normalized name, embedding similarity >0.85
- LLM verification for borderline clusters (confidence 0.4–0.7)
- `ResolutionCase` output with merge_decision + verification_trace
- Incremental: resolve against existing graph entities

#### Phase G5 — Multi-Resolution Leiden + PageRank (Feature #4)
**Files: ~2 | Lines: ~300**

- Leiden at γ=0.5, 1.0, 2.0 → 3-level hierarchy
- `parent_community_id` linking
- `BELONGS_TO` edges (entity → community)
- `PARENT_OF` edges (community hierarchy)
- PageRank computation: store scores on entities
- Used for context budget prioritization

---

### Query Intelligence (G6–G9)

#### Phase G6 — Context Builder (Feature #8)
**Files: ~1 | Lines: ~350**

- N-hop expansion from anchor entities (default 2, configurable)
- Relation verbalization: "{source} {type} {target}: {description}"
- Top-k chunk attachment (cosine >0.7)
- Community summary attachment (Global mode)
- Token budget (default 2048): greedy by importance (PageRank + recency)
- Deduplication: overlapping chunks, duplicate descriptions
- Output: `ContextBundle` with evidence links

#### Phase G7 — Answer Tracing (Feature #12)
**Files: ~2 | Lines: ~300**

- `TraceRecorder`: logs every query through full pipeline
- `query_traces` PostgreSQL table
- `AnswerTrace`: QueryPlan + ContextBundle + LLM model + tokens + latency + cache + ACL filtered
- API: `GET /v1/traces/{id}`, `GET /v1/traces`
- Optional `?trace=true` on search/graphrag endpoints
- `MetricEvent` storage in PostgreSQL for replay analysis

#### Phase G8 — Enhanced Router (25 Rules + Full Dynamic Override)
**Files: ~2 | Lines: ~250**

- 25 routing rules in YAML (spec provides examples)
- Stage 2: fine-tuned MiniLM-L6 (training infra exists, needs model training)
- Stage 3 enhanced override conditions:
  - Graph coverage (entity density <0.1) → BASIC
  - ACL filtered >50% nodes → HYBRID
  - Token budget <512 → BASIC
  - System load >0.7 → BASIC
  - Cache hit for different mode → redirect
  - User feedback history → demote poor-performing mode
- Optional: lightweight LLM override (Ollama 3B few-shot)

#### Phase G9 — Cache + Report Enrichment
**Files: ~2 | Lines: ~250**

- Cache key: `{mode}:{query_hash}:{acl_fingerprint}:{graph_version}:{embedding_version}:{prompt_version}`
- TTL: Basic=15m, Local=10m, Global=60m, DRIFT=5m, Hybrid=10m
- Invalidation triggers: source re-ingested, extraction rerun, entity merge, ACL change, graph rebuild, prompt change
- Community report enrichment: key_entities, key_relations, evidence_links, freshness_timestamp, model_version
- Report embedding for cosine pre-filtering in Global search

---

### Schema + Storage (G10)

#### Phase G10 — PostgreSQL + Neo4j Schema Merge
**Files: ~2 | Lines: ~300**

PostgreSQL additions:
- `entity_search` (FTS on names + aliases)
- `graph_build_jobs`
- `community_runs`
- `query_traces`
- `node_acls` (merge with existing acl_snapshots)
- `cache_invalidation_log`
- `metric_events`
- `evaluations` (LLM judge scores)
- Enable pgvector extension + chunk embedding column + IVFFlat index

Neo4j DDL (adopt spec verbatim):
- Constraints: entity_id, relation_id, community_id unique
- Indexes: entity_name, entity_type, entity_acl, relation_type, relation_acl, community_level
- BELONGS_TO edges, PARENT_OF edges

---

### Advanced Extraction (G11)

#### Phase G11 — Schema-Guided Extraction (OpenSPG/KAG)
**Files: ~3 | Lines: ~400**

- `graphrag/extraction/schema_extractor.py` — ontology-guided extraction:
  - Load schema definition (YAML/JSON): allowed entity types, relationship types, constraints
  - Feed schema + text to LLM: "Extract ONLY entities matching this schema"
  - Validate extracted entities against schema (type checking, cardinality)
  - Used for regulated domains: legal, medical, financial
- `graphrag/extraction/schemas/` — directory for domain schemas
  - `default.yaml` — general purpose
  - `legal.yaml` — contracts, clauses, parties, obligations
  - `medical.yaml` — conditions, treatments, medications
  - `financial.yaml` — entities, transactions, regulations
- Hybrid mode: regex first → LLM for unmatched → schema validation

---

### Observability (G12)

#### Phase G12 — Full Observability Stack (Prometheus + OpenTelemetry + Grafana)
**Files: ~3 | Lines: ~350**

- `omnirag/observability/prometheus.py` — production Prometheus exporter:
  - 8 mandatory metric families from spec
  - Proper histogram buckets, counter labels
  - `/metrics` endpoint in Prometheus text format
- `omnirag/observability/tracing.py` — OpenTelemetry integration:
  - W3C traceparent propagation
  - Span types: extraction, resolution, graph_build, community, retrieval, rerank, generation, consistency
  - Configurable sampling rate (default 1%)
- `omnirag/observability/logging.py` — structured JSON logging:
  - Fields: timestamp, request_id, user_principal_hash, query, mode, latency_ms, fallback_used, error
  - Levels: INFO (sampled 1:100), WARN (fallbacks), ERROR (persistent failures)
- Docker Compose: add Grafana + Prometheus services on ports 8180–8189

---

### pgvector Integration (G13)

#### Phase G13 — PostgreSQL pgvector as Vector Store
**Files: ~2 | Lines: ~300**

- `output/index_writers/pgvector.py` — new vector writer:
  - Uses PostgreSQL+pgvector instead of (or alongside) Qdrant
  - `chunks.embedding vector(384)` column
  - IVFFlat index with cosine distance
  - ACL filtering via `WHERE acl_principals && $1`
  - Full-text search via `tsvector` column + GIN index
  - Single DB for vectors + FTS + metadata (spec's approach)
- Update hybrid retriever to support pgvector as vector source
- Config: `VECTOR_STORE=pgvector|qdrant` (user's choice)

---

### Workflow Runtime (G14)

#### Phase G14 — LangGraph + AutoGen Integration
**Files: ~5 | Lines: ~600**

- `omnirag/workflows/__init__.py` — workflow runtime package
- `omnirag/workflows/langgraph_runner.py` — LangGraph integration:
  - Define stateful workflows: ingest → extract → build → query
  - Persistent state (PostgreSQL-backed checkpoints)
  - Subgraph support: extraction workflow, query workflow, evaluation workflow
  - Built-in workflows:
    - `full_ingestion` — source → parse → chunk → extract → resolve → build graph → communities → reports
    - `query_pipeline` — route → retrieve → context → reason → trace
    - `evaluation` — query → answer → LLM judge → score
- `omnirag/workflows/autogen_agents.py` — AutoGen multi-agent:
  - Roles: Researcher (searches graph), Analyst (synthesizes), Reviewer (validates)
  - Collaboration: Researcher finds entities → Analyst builds narrative → Reviewer checks citations
  - Config: agent roles, models, conversation flow
- `omnirag/workflows/definitions.py` — workflow YAML definitions
- API: `POST /v1/workflows/run`, `GET /v1/workflows/{id}/status`

---

### Frontend (G15–G16)

#### Phase G15 — Next.js Frontend
**Files: ~15 | Lines: ~2,000**

Full Next.js app replacing vanilla JS shell:

```
frontend/
  app/
    layout.tsx          — shell (sidebar + tabs + footer)
    page.tsx            — home (RAG tab)
    omnigraph/page.tsx  — OmniGraph tab
    graph/page.tsx      — Graph Explorer tab
    chat/page.tsx       — Chat tab
    settings/page.tsx   — Settings
    api-docs/page.tsx   — embedded Swagger
  components/
    shell/              — sidebar rail, panel, drawer, titlebar
    chat/               — message bubbles, composer, toolbar
    graph/              — entity search, community browser, relationship viewer
    intake/             — source input, file picker, job list
    adapters/           — adapter cards, config forms, test buttons
  lib/
    api.ts              — typed API client
    types.ts            — TypeScript types matching Python models
  styles/
    globals.css         — dark theme (current CSS ported to Tailwind)
```

- Server-side rendering for initial load
- React Query for data fetching
- React Flow for graph visualization (node/edge rendering)
- Responsive: mobile drawer, tablet rail, desktop panel (our shell pattern)
- Dark theme matching current design

#### Phase G16 — Chainlit Ops UI
**Files: ~5 | Lines: ~500**

```
ops-ui/
  app.py              — Chainlit app
  handlers/
    query.py           — interactive query with trace visualization
    ingest.py          — monitor ingestion jobs
    graph.py           — browse graph, inspect entities
  utils/
    api_client.py      — OmniRAG API wrapper
```

- Chat-based ops interface for debugging
- Trace inspection: see QueryPlan → ContextBundle → LLM call → Answer
- Ingestion monitoring: job progress, errors, document counts
- Graph browsing: entity lookup, community reports, relationship paths
- Docker service on port 8170

---

### Tool Protocol (G17)

#### Phase G17 — MCP (Model Context Protocol)
**Files: ~3 | Lines: ~400**

- `omnirag/mcp/__init__.py` — MCP server
- `omnirag/mcp/tools.py` — exposed tools:
  - `search_knowledge_graph` — entity lookup, neighborhood traversal
  - `search_documents` — vector + keyword hybrid search
  - `get_community_report` — fetch community summary
  - `ingest_document` — trigger intake pipeline
  - `get_entity_details` — entity properties, aliases, relationships
- `omnirag/mcp/resources.py` — exposed resources:
  - Graph stats, pipeline status, recent traces
- API: MCP-compatible endpoint for LLM tool use
- Compatible with: Claude, GPT-4, any MCP-aware model

---

### LlamaIndex Integration (G18)

#### Phase G18 — LlamaIndex Property Graph Index
**Files: ~3 | Lines: ~400**

- `omnirag/integrations/llamaindex.py` — LlamaIndex bridge:
  - Expose OmniRAG's Neo4j graph as LlamaIndex `PropertyGraphIndex`
  - Support schema-guided extraction via LlamaIndex `SchemaLLMPathExtractor`
  - Support free-form extraction via `DynamicLLMPathExtractor`
  - Multi-retriever: vector similarity + keyword + Cypher traversal
  - Compatible with LlamaIndex query engine
- `omnirag/integrations/llamaindex_store.py` — graph store adapter:
  - Maps OmniRAG's Neo4j wrapper to LlamaIndex's `Neo4jPropertyGraphStore`
- Config: `LLAMAINDEX_ENABLED=true` enables the bridge

---

### Analytics (G19)

#### Phase G19 — Power BI Connector + Analytics Export
**Files: ~2 | Lines: ~250**

- `omnirag/integrations/powerbi.py` — Power BI REST API connector:
  - Export entity/relationship data as tabular datasets
  - Push community reports + metrics to Power BI service
  - Scheduled refresh via API token
- `api/routes/analytics.py` — analytics endpoints:
  - `GET /v1/analytics/entities` — entity table (name, type, connections, PageRank)
  - `GET /v1/analytics/communities` — community table (level, size, report summary)
  - `GET /v1/analytics/queries` — query trace aggregates (mode distribution, latency percentiles)
  - `GET /v1/analytics/quality` — evaluation scores over time
  - All support CSV/JSON/Parquet export

---

## Full Scope Summary

| Phase | Focus | Files | Lines |
|-------|-------|-------|-------|
| G1 | Canonical data model | 2 | ~400 |
| G2 | 23 service contracts | 1 | ~300 |
| G3 | LLM extraction (4 modes) | 4 | ~600 |
| G4 | Entity resolution + LLM verify | 1 | ~200 |
| G5 | Multi-resolution Leiden + PageRank | 2 | ~300 |
| G6 | Context Builder | 1 | ~350 |
| G7 | Answer tracing | 2 | ~300 |
| G8 | Enhanced router (25 rules) | 2 | ~250 |
| G9 | Cache + report enrichment | 2 | ~250 |
| G10 | PostgreSQL + Neo4j schema | 2 | ~300 |
| G11 | Schema-guided extraction (OpenSPG/KAG) | 3 | ~400 |
| G12 | Full observability (Prometheus + OTel + Grafana) | 3 | ~350 |
| G13 | pgvector as vector store | 2 | ~300 |
| G14 | LangGraph + AutoGen workflows | 5 | ~600 |
| G15 | Next.js frontend | 15 | ~2,000 |
| G16 | Chainlit Ops UI | 5 | ~500 |
| G17 | MCP Tool Protocol | 3 | ~400 |
| G18 | LlamaIndex Property Graph | 3 | ~400 |
| G19 | Power BI + analytics | 2 | ~250 |
| **Total** | | **~60** | **~8,450** |

---

## Build Order

```
FOUNDATION:     G1 → G2

CORE QUALITY:   G3 → G4 → G5

QUERY:          G6 → G7 → G8 → G9

STORAGE:        G10 → G13

EXTRACTION:     G11

OBSERVABILITY:  G12

WORKFLOWS:      G14

FRONTEND:       G15 → G16

INTEGRATIONS:   G17 → G18 → G19
```

Parallelizable groups:
- G3+G10 (extraction + schema — independent)
- G11+G12 (schema extraction + observability — independent)
- G15+G16+G17 (frontend + ops UI + MCP — independent of each other)
- G18+G19 (LlamaIndex + Power BI — independent)

---

## After Full Implementation

```
Current OmniRAG:        ~100 files,   ~9,150 lines  ✅
OmniGraph Full (G1–G19): ~60 files,   ~8,450 lines  ← planned
──────────────────────────────────────────────────────────
Total:                  ~160 files,  ~17,600 lines

14/14 mandatory features implemented
12/12 services implemented
23/23 contracts defined
All tech stack components integrated
```

---

## Maturity After Full Implementation

```
[Toy] ─── [Prototype] ─── [MVP] ─── [Production] ─── [Enterprise]
                                                          ▲
                                                     After G1–G19
```

Full enterprise-grade GraphRAG platform. Nothing deferred. Nothing skipped.

Awaiting approval to proceed.
