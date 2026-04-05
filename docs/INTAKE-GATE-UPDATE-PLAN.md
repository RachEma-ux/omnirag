# Intake Gate Update Plan — Gap Analysis & Upgrade Roadmap

**Date:** 2026-04-05
**Input:** `RAG Intake Gate Document.md` + `RAG Intake Gate References Document.md`
**Current:** `omnirag/intake/` (Phase 0+1 basic implementation)
**Agent:** Planner (report before coding)

---

## Executive Summary

The reference documents describe a **governed intake control plane** — far more sophisticated than what we built. Our current intake is a simple `source → fetch → parse → normalize` pipe. The reference spec calls for a **12-state job state machine**, **3-type transport model** (Blob/Record/Event), **semantic materializers**, **ACL propagation**, **backpressure with circuit breakers**, **cursor-based incremental sync**, **reconciliation workers**, and a **full storage schema** with audit lineage.

This update will transform the intake from a basic importer into a governed control plane.

---

## Gap Analysis: What We Have vs What's Required

### Layer 1: Core Architecture

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| Connector interface | `fetch()` + `supports()` | `discover()` + `fetch()` + `changes()` + `subscribe()` + `permissions()` + `delete_events()` + `version()` | **6 missing methods** |
| Transport model | `RawContent` (bytes only) | `BlobAsset` + `RecordAsset` + `EventAsset` | **Missing Record + Event types** |
| Normalized output | `OmniDocument` (flat) | `SourceObject` → `CanonicalDocument` with semanticType + provenance + ACL | **Missing SourceObject layer, ACL, provenance** |
| Job state machine | 5 states (pending/fetching/loading/normalizing/complete/failed) | **12 active + 5 terminal states** (REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED → MATERIALIZED → ENRICHED → ACL-BOUND → CHUNKED → INDEXED → VERIFIED → ACTIVE + DEFERRED/FAILED/TOMBSTONED/REVOKED/QUARANTINED) | **Major gap** |
| Auth/Secret broker | Config dict passed inline | Auth ref to secret store with least-privilege scopes | **Missing** |
| Policy engine | None | File-type policy, size caps, PII rules, crawl rules | **Missing** |
| Cursor/checkpoint store | None | Per-connector cursor with atomic updates for incremental sync | **Missing** |
| Event bus | None | Job lifecycle events for observability | **Missing** |

### Layer 2: Backpressure & Flow Control

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| Rate limits | None | Per-connector: docsPerMinute, chunksPerSecond, concurrentFetchers, batchSize | **Missing** |
| Token bucket | None | Leaky bucket per connector | **Missing** |
| Admission controller | None | Global limits + per-connector concurrency + indexer health check | **Missing** |
| Backpressure registry | None | Collects health from index writers | **Missing** |
| Circuit breakers | None | Per-indexer, failure threshold, half-open recovery | **Missing** |
| Adaptive batching | None | Batch size adjusts based on write latency | **Missing** |
| DEFERRED state | None | Jobs pause and retry with exponential backoff (2,4,8,16,32s, max 5 attempts) | **Missing** |
| Dead-letter queue | None | Jobs that fail after 5 retries → dead_letters table | **Missing** |

### Layer 3: Extraction & Materialization

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| Extractor registry | Loaders (text, pdf, docx, html) | Extractors with `ExtractedContent` (text + structure + metadata + confidence) | **Missing structure + confidence** |
| Semantic materializers | None | document, table, code, conversation, email, webpage, notebook, event_window | **Missing entirely** |
| Type-aware chunkers | None | Per-semantic-type chunker (heading-aware, symbol-aware, turn-based, etc.) | **Missing entirely** |
| Quality scoring | None | Confidence score per extraction | **Missing** |
| PII detection | None | PII/secret scanning before indexing | **Missing** |

### Layer 4: Permissions & Lineage

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| ACL capture | None | `permissions()` on connector, snapshot stored | **Missing** |
| ACL propagation | None | ACL attached to every CanonicalDocument and Chunk | **Missing** |
| Permission revocation | None | Reconciliation detects changes → REVOKED → re-index | **Missing** |
| Lineage/audit | None | Full traceability: chunk → document → source object → connector | **Missing** |
| Tombstones | None | Soft-delete for removed sources | **Missing** |
| Reconciliation | None | Periodic worker compares source vs indexed state | **Missing** |

### Layer 5: Storage

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| Storage | In-memory dicts | PostgreSQL: 12+ tables (connectors, sync_jobs, source_cursors, source_objects, canonical_documents, chunks, acl_snapshots, dead_letters, tombstones, backpressure_events, indexer_health_snapshots) | **Missing all persistent storage** |
| Raw object store | None | S3/MinIO bucket for raw bytes | **Missing** |
| Vector index writes | None | Chunk → vector DB + keyword index + metadata + audit | **Missing** |

### Layer 6: API & Observability

| Component | Current State | Reference Spec | Gap |
|-----------|--------------|----------------|-----|
| API | `POST /intake`, `GET /intake/{id}` | Full REST: connectors CRUD, jobs with filters, retry, backpressure health, circuit breaker status, webhook receiver | **Mostly missing** |
| Prometheus metrics | None | intake_jobs_active, intake_jobs_deferred, indexer_queue_depth, indexer_latency_ms, circuit_breaker_state, token_bucket_remaining | **Missing** |
| UI surfaces | None | Connectors, Policies, Runs, Content Explorer, Lineage, Backpressure Dashboard | **Missing** |

---

## Upgrade Roadmap (Ordered by Impact)

### Phase A — Core Contract Upgrade (Critical)
**Impact: Foundation for everything else**

1. **Upgrade SourceObject model** — Add `SourceObject` as intermediate between RawContent and CanonicalDocument with `objectKind` (blob/record/event), checksum, versionRef, parentRef, timestamps, aclSnapshotRef
2. **Upgrade CanonicalDocument** — Add `semanticType`, `provenance`, `acl`, `structure` fields
3. **Upgrade Chunk model** — Add `order`, `sectionPath`, `aclFilterRef`, `embeddingRef`
4. **Expand Connector interface** — Add `discover()`, `changes()`, `subscribe()`, `permissions()`, `delete_events()`, `version()` with default no-op implementations
5. **Add Connector config model** — capabilities, rateLimits, backpressure, bulkImport
6. **Add ACL model** — principals, groups, visibility, sourceScope

### Phase B — Job State Machine (Critical)
**Impact: Predictable lifecycle for every ingest**

7. **12-state machine** — REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED → MATERIALIZED → ENRICHED → ACL-BOUND → CHUNKED → INDEXED → VERIFIED → ACTIVE
8. **Terminal states** — DEFERRED, FAILED, TOMBSTONED, REVOKED, QUARANTINED
9. **SyncJob model** — trigger, attempt, cursorKey, deferredUntil
10. **Cursor store** — per-connector checkpoint persistence

### Phase C — Backpressure & Flow Control (High)
**Impact: Prevents firehose at scale**

11. **Token bucket** — per-connector rate limiter
12. **Admission controller** — global + per-connector + indexer health gates
13. **Backpressure registry** — collects indexer health signals
14. **Circuit breakers** — per-indexer, auto-open/close
15. **DEFERRED + exponential backoff** — 2,4,8,16,32s, max 5 attempts → dead-letter
16. **Dead-letter queue** — persistent store + replay API

### Phase D — Semantic Layer (High)
**Impact: Quality of retrieval**

17. **Extractor registry** — replace Loaders with Extractors producing `ExtractedContent` (text + structure + confidence)
18. **Semantic materializers** — document, table, code, conversation, email, webpage, notebook, event_window
19. **Type-aware chunkers** — heading-aware, symbol-aware (tree-sitter), turn-based, row-group, DOM-section, cell-group, time-window

### Phase E — Permissions & Reliability (Medium)
**Impact: Enterprise readiness**

20. **ACL snapshotting** — capture at ingest, store in acl_snapshots
21. **ACL propagation** — attach to every document and chunk
22. **Tombstones** — soft-delete on source removal
23. **Reconciliation worker** — periodic compare source vs indexed
24. **Idempotency keys** — connectorId + externalId + versionRef
25. **Lineage events** — full audit trail

### Phase F — Storage Schema (Medium)
**Impact: Persistence**

26. **PostgreSQL tables** — connectors, sync_jobs, source_cursors, source_objects, canonical_documents, chunks, acl_snapshots, dead_letters, tombstones, backpressure_events, indexer_health_snapshots
27. **Raw object store** — local disk or S3/MinIO for raw bytes
28. **Index writer abstraction** — write chunks to vector DB + keyword index

### Phase G — API & Observability (Lower)
**Impact: Operability**

29. **Full REST API** — connectors CRUD, sync trigger, job list/retry, backpressure health, circuit breaker management, webhook receiver
30. **Prometheus metrics** — all 6 metric families
31. **UI surfaces** — Connectors, Runs, Content Explorer, Lineage, Backpressure Dashboard

---

## What Stays Unchanged

- **Connector implementations** (local, http, s3, github) — keep, but upgrade to new interface
- **Loader implementations** (text, pdf, docx, html) — keep, rename to Extractors
- **Format detector** — keep as-is
- **API route structure** — keep /intake, extend with /connectors, /jobs, etc.
- **Frontend shell** — keep, add new UI pages later

---

## Estimated Scope

| Phase | Files | Lines (est) | Priority |
|-------|-------|-------------|----------|
| A — Core contracts | 6 | ~400 | Critical |
| B — State machine | 4 | ~300 | Critical |
| C — Backpressure | 5 | ~500 | High |
| D — Semantic layer | 8 | ~600 | High |
| E — Permissions | 5 | ~400 | Medium |
| F — Storage | 3 | ~500 | Medium |
| G — API/UI | 4 | ~400 | Lower |
| **Total** | **~35** | **~3,100** | — |

---

## Recommendation

Start with **Phase A + B** (core contracts + state machine) — this is the foundation. Everything else builds on it. The current connectors and loaders can be upgraded incrementally as the new contracts are available.

Shall I proceed with Phase A + B?
