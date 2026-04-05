# RAG Output Layer — Execution Plan

**Date:** 2026-04-05
**Input:** `RAG Output Layer.md` (RAG-OUT-SPEC-002 v2.0) + `RAG Output Layer – Technical Reference.md` (RAG-TR-OUT-001 v2.0)
**Upstream:** Universal Intake Gate (Phase A–G, complete)
**Agent:** Planner (report only, no code)

---

## What the Spec Requires

The output layer consumes chunks from the intake gate and provides:

1. **Embedding Pipeline** — chunks → vectors (async, Kafka-driven, batched 256, retry with backoff, DLQ)
2. **Vector Database** — Qdrant (384-dim, cosine, HNSW, ACL payload filtering)
3. **Keyword Index** — Elasticsearch (BM25, english analyzer, ACL terms filter)
4. **Metadata Store** — PostgreSQL (chunks, documents, lineage_edges, GIN index on ACL)
5. **Consistency Coordinator** — Redis (global index_version, per-store versions, polling for read-after-write)
6. **Retrieval Layer** — hybrid search (vector + keyword → RRF k=60 → cross-encoder reranking → top-K with ACL filtering, graceful degradation)
7. **Generation Layer** — LLM adapters (ollama/openai) with citation-aware prompt template + citation extraction from output
8. **Delivery APIs** — REST (POST /v1/search), WebSocket streaming (SSE tokens + citations), Webhooks (intake events), Export (JSONL/CSV/Parquet), Audit/Lineage
9. **Observability** — Prometheus metrics (7 metric families), structured JSON logging, Jaeger tracing (4 span types)
10. **Security** — JWT RS256, ACL evaluation pushed to all 3 stores, rate limiting (Redis sliding window), audit logging to immutable store

---

## Gap Analysis: What OmniRAG Has vs What's Required

| Component | Current State | Required | Gap |
|-----------|--------------|----------|-----|
| Embedding pipeline | HuggingFace adapter exists but not wired to intake chunks | Async pipeline: chunk → embed → write to vector DB, batch 256, retry, DLQ | **Major** |
| Vector DB | Qdrant adapter exists (store/retrieve) but standalone | ACL-filtered vector search, payload indexing, quorum writes | **Major** |
| Keyword index | None | Elasticsearch with BM25, ACL filter, english analyzer | **Missing** |
| Metadata store | PostgreSQL schema exists (intake Phase F) but no output tables | chunks + documents + lineage_edges tables with GIN ACL index, stored procedures | **Partial** |
| Consistency coordinator | None | Redis index versioning, per-store tracking, polling with timeout | **Missing** |
| Retrieval layer | Memory adapter (basic top-K) | Hybrid search (vector + BM25), RRF fusion, cross-encoder reranking, ACL pre-filter, fallback matrix | **Major** |
| Generation layer | ollama_gen + openai_gen adapters exist | Citation-aware prompt template, citation extraction regex, structured answer response | **Partial** |
| REST API | POST /pipelines/{name}/invoke | POST /v1/search with ACL, filters, read_your_writes, response headers | **Major** |
| WebSocket | Stub exists | Streaming tokens + citations + end event, JWT auth via query param | **Major** |
| Webhooks | None | Registration, HMAC-signed delivery, retry with backoff, DLQ | **Missing** |
| Export API | None | GET /v1/export/{format} (JSONL/CSV/Parquet), ACL-filtered, paginated, streaming download | **Missing** |
| Audit/Lineage API | Lineage store exists (intake Phase E) | GET /v1/lineage/chunk/{id}, GET /v1/lineage/answer/{id} | **Partial** |
| Prometheus metrics | Basic metrics in observability module | 7 metric families: indexed_total, query_latency, fallback_total, rate_limit_hits, consistency_wait, websocket_connections, webhook_delivery | **Partial** |
| Rate limiting | None | Redis sliding window, per-user limits, X-RateLimit headers, 429 response | **Missing** |
| JWT auth | None (dev mode bypass) | RS256 JWT validation, principal extraction, scope enforcement | **Missing** |
| Tracing | None | Jaeger W3C traceparent, 4 span types | **Missing** |

---

## Execution Plan (8 Phases)

### Phase H — Embedding Pipeline + Index Writers
**Impact: Connects intake output to searchable indexes**
**Files: ~6 | Lines: ~500**

1. `output/embedding.py` — EmbeddingWorker
   - Consumes chunks from intake gate (in-process for now, Kafka interface ready)
   - Batch 256 chunks → model.encode() → vectors
   - Retry: exponential backoff (100ms, 200ms, 400ms), max 3 attempts
   - DLQ for permanent failures
   - Status tracking: embedding_status ∈ {pending, completed, failed}

2. `output/index_writers/vector.py` — VectorIndexWriter
   - Qdrant adapter: upsert with ACL payload, idempotent by chunk_id
   - Collection: chunk_embeddings, 384-dim, cosine, HNSW(m=16, ef=200)
   - Payload: chunk_id, doc_id, acl_principals, metadata
   - Fallback: in-memory vector store when Qdrant unavailable

3. `output/index_writers/keyword.py` — KeywordIndexWriter
   - Elasticsearch adapter: bulk index with english analyzer
   - ACL terms filter on acl_principals
   - Fallback: PostgreSQL full-text search when ES unavailable

4. `output/index_writers/metadata.py` — MetadataIndexWriter
   - PostgreSQL: chunks, documents, lineage_edges tables
   - GIN index on acl_principals
   - Stored procedure: get_visible_chunks(user_principals)

5. Wire INDEXED state in intake gate to call all 3 writers

### Phase I — Consistency Coordinator
**Impact: Read-after-write guarantee**
**Files: ~2 | Lines: ~200**

6. `output/consistency.py` — ConsistencyCoordinator
   - Redis keys: global:index_version, store:{vector,keyword,metadata}:version
   - Commit protocol: INCR + SET after batch write
   - Polling: 50ms interval, 500ms max wait
   - Timeout → X-Consistency: eventual header
   - User version tracking: per user_principal_hash in Redis

### Phase J — Retrieval Layer
**Impact: Core search quality**
**Files: ~4 | Lines: ~600**

7. `output/retrieval/hybrid.py` — HybridRetriever
   - Parallel: vector search (Qdrant, 2×top_k) + keyword search (ES, 2×top_k)
   - ACL pre-filter pushed to both stores
   - RRF fusion (k=60)

8. `output/retrieval/reranker.py` — CrossEncoderReranker
   - cross-encoder/ms-marco-MiniLM-L-6-v2
   - Score top 50 fused candidates → return top_k
   - Fallback: skip reranking, return RRF results

9. `output/retrieval/fallback.py` — FallbackManager
   - Decision matrix: 5 failure scenarios
   - Vector down → keyword only + X-Fallback header
   - ES down → vector only
   - Both down → HTTP 503
   - Reranker down → skip rerank
   - ACL store down → HTTP 500 (cannot authorize)
   - All fallbacks instrumented as metrics

10. `output/retrieval/evidence.py` — EvidenceBundle builder
    - Assembles mode, chunks with scores (vector, bm25, rrf), fallback info, latency

### Phase K — Generation Layer (Citation-Aware)
**Impact: Answer quality + traceability**
**Files: ~3 | Lines: ~300**

11. `output/generation/prompt.py` — PromptBuilder
    - Citation-aware template: "Answer using ONLY chunks. Cite as [doc_id:chunk_id]."
    - Formats chunks with provenance

12. `output/generation/adapter.py` — LLMAdapter ABC + OpenAI + Ollama implementations
    - generate(query, chunks) → (answer, citations)
    - Reuse existing adapters, add citation interface

13. `output/generation/citation.py` — CitationExtractor
    - Regex: `\[([a-f0-9\-]+):([a-f0-9\-]+)\]`
    - Validate against input chunks
    - Format as structured citations with snippets

### Phase L — Delivery APIs
**Impact: User-facing interfaces**
**Files: ~5 | Lines: ~600**

14. `api/routes/search.py` — POST /v1/search
    - Full pipeline: ACL filter → hybrid search → rerank → generate → respond
    - Request: query, top_k, filters, read_your_writes
    - Response: answer, citations, metadata (latency, mode, consistency)
    - Headers: X-Consistency, X-Fallback, X-RateLimit-*

15. `api/routes/search.py` — POST /v1/search/debug (admin only)
    - Returns intermediate retrieval results (vector scores, keyword scores, RRF, reranker)

16. `api/routes/stream.py` — WebSocket /v1/stream
    - JWT auth via ?token= query param
    - Client: {query, top_k, filters}
    - Server: {type:token}, {type:citation}, {type:end}
    - 10 concurrent streams per user

17. `api/routes/webhooks.py` — POST /v1/webhooks + delivery dispatcher
    - Registration: url, events, HMAC secret
    - Delivery: POST with signed payload
    - Retry: exponential backoff (1,2,4,8,16s), max 5
    - DLQ for permanent failures

18. `api/routes/export.py` — GET /v1/export/{format}
    - Formats: jsonl, csv, parquet
    - ACL-filtered, paginated (max 100K rows)
    - Streaming download with Content-Disposition

19. `api/routes/lineage_api.py` — Audit/Lineage endpoints
    - GET /v1/lineage/chunk/{chunk_id} — provenance chain
    - GET /v1/lineage/answer/{answer_id} — chunks used for answer

### Phase M — Observability
**Impact: Operational visibility**
**Files: ~2 | Lines: ~250**

20. `output/metrics.py` — Prometheus metrics (7 families)
    - rag_chunks_indexed_total (counter, by store + status)
    - rag_query_latency_seconds (histogram, by mode + fallback)
    - rag_retrieval_fallback_total (counter, by from + to)
    - rag_rate_limit_hits_total (counter, by endpoint)
    - rag_consistency_wait_seconds (histogram)
    - rag_websocket_connections (gauge)
    - rag_webhook_delivery_seconds (histogram, by status)

21. `output/tracing.py` — Jaeger integration
    - W3C traceparent propagation
    - 4 span types: retrieval.hybrid_search, retrieval.rerank, generation.llm_call, consistency.wait

### Phase N — Security & Rate Limiting
**Impact: Production readiness**
**Files: ~3 | Lines: ~350**

22. `output/auth.py` — JWT validation
    - RS256 signature verification
    - Claims: sub, principal, roles, scopes
    - Extract user_principals: [principal] + [role:x for x in roles]
    - Scope enforcement: rag:search, rag:export, rag:admin

23. `output/rate_limiter.py` — Redis sliding window
    - Per-user limits: search 100/min, export 10/hour, WS 10 concurrent
    - X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers
    - 429 with Retry-After on exceeded
    - Admin override: redis key rate_limit:override:{principal}

24. `api/middleware/security.py` — FastAPI middleware
    - JWT extraction from Authorization header
    - Rate limit check before handler
    - Inject user_principals into request state

### Phase O — Storage Schema (Output Layer)
**Impact: Persistence for output components**
**Files: ~1 | Lines: ~100**

25. `output/storage/schema.sql` — Output-specific PostgreSQL tables
    - chunks (output version: embedding_status, content_hash)
    - documents (output: source_uri, ingestion_ts)
    - lineage_edges (chunk_id → parent_uri, transformation)
    - webhook_registrations, webhook_deliveries
    - answer_logs (for lineage/answer endpoint)
    - Indexes: GIN on acl_principals, BTREE on doc_id, status

---

## Rollout Plan (from spec)

| Phase | Components | Acceptance Criteria |
|-------|-----------|-------------------|
| **P0** | Vector DB, Keyword Index, Metadata Store, Retrieval (hybrid), REST API (no auth) | End-to-end query returns correct chunks |
| **P1** | Authentication, rate limiting, Prometheus metrics | Auth enforced; rate limit headers present |
| **P2** | Fallback logic, consistency coordinator, WebSocket streaming | Simulated store failure falls back; read-after-write works |
| **P3** | Webhooks, Export API, Audit/Lineage API | Webhook delivery succeeds; export generates files |

### Mapping to our phases:

| Rollout | Our Phases |
|---------|-----------|
| P0 | H (index writers) + J (retrieval) + K (generation) + L (search API) |
| P1 | N (security + rate limiting) + M (metrics) |
| P2 | I (consistency) + J (fallback) + L (WebSocket) |
| P3 | L (webhooks + export) + L (lineage API) |

---

## Dependencies (new packages)

```toml
[project.optional-dependencies]
output-core = [
  "sentence-transformers>=2.5",    # embedding model
  "qdrant-client>=1.7",            # vector DB
  "elasticsearch[async]>=8.5",     # keyword index
  "redis>=5.0",                    # consistency + rate limiting
]
output-generation = [
  "openai>=1.0",                   # OpenAI adapter
]
output-export = [
  "pyarrow>=15.0",                 # Parquet export
]
output-tracing = [
  "opentelemetry-api>=1.20",
  "opentelemetry-sdk>=1.20",
  "opentelemetry-exporter-jaeger>=1.20",
]
output-all = [
  "omnirag[output-core,output-generation,output-export,output-tracing]",
]
```

---

## Estimated Scope

| Phase | Focus | Files | Lines (est) | Priority |
|-------|-------|-------|-------------|----------|
| H | Embedding + Index Writers | 6 | ~500 | Critical |
| I | Consistency Coordinator | 2 | ~200 | High |
| J | Retrieval (hybrid + rerank + fallback) | 4 | ~600 | Critical |
| K | Generation (citation-aware) | 3 | ~300 | Critical |
| L | Delivery APIs (search, WS, webhooks, export, lineage) | 5 | ~600 | Critical |
| M | Observability (metrics + tracing) | 2 | ~250 | High |
| N | Security (JWT + rate limiting + middleware) | 3 | ~350 | High |
| O | Storage Schema (output tables) | 1 | ~100 | Medium |
| **Total** | | **~26** | **~2,900** | |

---

## Summary

8 phases, ~26 files, ~2,900 lines. Combined with the intake gate (33 files, 2,840 lines), the full RAG platform will be ~59 files, ~5,740 lines — a complete governed intake + output control plane.

Build order recommendation: **H → J → K → L (P0 first)**, then **N → M (P1)**, then **I → L-websocket (P2)**, then **L-webhooks + L-export (P3)**, then **O**.

Awaiting approval to proceed.
