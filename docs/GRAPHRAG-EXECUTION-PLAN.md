# GraphRAG — Execution Plan

**Date:** 2026-04-05
**Input:** `GraphRAG Production Architecture Specification.md` (v1.0) + `GraphRAG Technical Reference.md` (GR-TR-001 v1.0)
**Upstream:** Universal Intake Gate (A–G) + Output Layer (H–O) + Wiring (complete)
**Agent:** Planner (report only, no code)

---

## What the Spec Requires

A **graph sidecar** that sits alongside the existing vector/keyword RAG fabric, consuming canonical chunks from the intake gate, building a knowledge graph in Neo4j, and enabling three additional query modes (Local, Global, DRIFT) through an intelligent query router.

### Core Components:

1. **Graph Projection Service** — entity extraction, entity resolution (HDBSCAN clustering), relationship extraction (weighted), community detection (Leiden), community report generation (LLM)
2. **Graph Store** — Neo4j with 5 node types (Document, Chunk, Entity, Community, CommunityReport), 5 edge types (HAS_CHUNK, MENTIONS, RELATES_TO, IN_COMMUNITY, HAS_REPORT), ACL on every node/edge
3. **Incremental Community Updates** — chunk→community mapping, staleness scoring, delta-based Leiden recompute, nightly full rebuild fallback
4. **Entity Resolution** — embed mentions → HDBSCAN clustering → canonical name selection → optional Wikidata linkage → Redis alias map
5. **Graph Query Service** — 3 modes:
   - **Local**: entity-centric, graph traversal + linked chunks
   - **Global**: map-reduce over community reports (resource-intensive)
   - **DRIFT**: global→extract entities→local refinement
6. **Query Router** — 3-stage: rule-based patterns → BERT classifier (distilbert, 4 classes) → dynamic override (confidence/coverage thresholds)
7. **Fusion** — all modes normalize to `EvidenceBundle` with chunks, entities, relationships, community reports, confidence, coverage → cross-encoder rerank → LLM answer with citations
8. **Caching** — Redis with mode-specific TTLs (Global: 1h, Local/DRIFT: 5m), invalidation on community report changes
9. **Observability** — 8 Prometheus metrics (latency, confidence, coverage, routing, cache, community updates, LLM tokens, stale count), structured logging, Jaeger tracing
10. **API** — 4 endpoints: `/graphrag/query/{local,global,drift,route}`, all ACL-enforced, cache headers

---

## Gap Analysis: What OmniRAG Has vs What's Required

| Component | Current State | Required | Gap |
|-----------|--------------|----------|-----|
| Graph store | None | Neo4j with 5 node types, 5 edge types, ACL on all, Cypher constraints + indexes | **Missing entirely** |
| Entity extraction | None | spaCy NER with custom labels (PERSON, ORG, PRODUCT, PROJECT, REGULATORY_TERM) | **Missing** |
| Entity resolution | None | Embedding + HDBSCAN → clustering → canonical name → Redis alias map | **Missing** |
| Relationship extraction | None | DistilBERT relation model, co-occurrence weighting (1.0 base, 0.5 decay, cap 5.0) | **Missing** |
| Community detection | None | Leiden algorithm (cdlib), hierarchical, incremental | **Missing** |
| Community reports | None | LLM-generated summaries per community (max 300 words) | **Missing** |
| Incremental updates | None | chunk_community + stale_communities tables, 5-min reconciliation, staleness >20% trigger | **Missing** |
| Graph query (Local) | None | Entity-centric Cypher traversal, max_hops, ACL-filtered, linked chunks | **Missing** |
| Graph query (Global) | None | Map-reduce over community reports, cosine pre-filter, LLM map + reduce | **Missing** |
| Graph query (DRIFT) | None | Global → extract top-3 entities → Local for each → merge with decay | **Missing** |
| Query router | None | 3-stage: YAML patterns → BERT classifier → dynamic override (confidence 0.62, coverage 0.45) | **Missing** |
| Fusion + rerank | HybridRetriever exists | Extend EvidenceBundle with entities, relationships, community reports | **Partial** |
| Caching | None for graph | Redis with mode-specific keys, TTL, invalidation on report changes | **Missing** |
| Observability | Output metrics exist | 8 graph-specific metrics, structured logging, Jaeger spans | **Partial** |
| API | /v1/search exists | 4 new /graphrag/query/* endpoints | **Missing** |
| ACL on graph | ACL system exists (intake) | Propagate to every Neo4j node/edge, Cypher WHERE clauses | **Missing** |

---

## Execution Plan (7 Phases)

### Phase P — Graph Store + Schema
**Impact: Foundation for all graph operations**
**Files: ~4 | Lines: ~350**

1. `graphrag/store.py` — Neo4j connection manager (with in-memory fallback using networkx)
2. `graphrag/schema.py` — Cypher DDL: constraints, indexes, ACL indexes
3. `graphrag/models.py` — GraphEntity, GraphRelationship, GraphCommunity, CommunityReport, GraphChunk dataclasses
4. `graphrag/acl.py` — ACL propagation to graph nodes/edges, union logic for multi-doc entities

### Phase Q — Graph Projection Service (Entity + Relationship + Community)
**Impact: Core graph building from chunks**
**Files: ~6 | Lines: ~700**

5. `graphrag/extraction/entities.py` — Entity extraction (spaCy NER or regex fallback)
6. `graphrag/extraction/resolution.py` — Entity resolution: embed → HDBSCAN → canonical name → Redis alias map
7. `graphrag/extraction/relationships.py` — Relationship extraction: co-occurrence weight (1.0 base, 0.5 decay, cap 5.0)
8. `graphrag/extraction/communities.py` — Community detection: Leiden algorithm (cdlib), hierarchical levels
9. `graphrag/extraction/reports.py` — Community report generation: LLM summarization (300 words max)
10. `graphrag/projection.py` — Projection service orchestrator: subscribes to intake events → runs extraction pipeline → writes to Neo4j

### Phase R — Incremental Community Updates
**Impact: Keeps graph fresh without full rebuilds**
**Files: ~2 | Lines: ~250**

11. `graphrag/incremental.py` — Incremental update engine:
    - chunk_community + stale_communities PostgreSQL tables
    - On chunk change: mark affected community stale
    - Every 5 min: recompute communities with staleness >20%
    - Delta-based Leiden with seed partitions for merge/split
    - Nightly full recompute fallback
12. `graphrag/storage.sql` — PostgreSQL tables: chunk_community, stale_communities

### Phase S — Graph Query Service (Local, Global, DRIFT)
**Impact: Three new retrieval modes**
**Files: ~4 | Lines: ~500**

13. `graphrag/query/local.py` — Local search:
    - Extract entities from query → resolve via alias map → Cypher traversal (max_hops=2) → ACL-filtered → collect chunks from MENTIONS edges → EvidenceBundle
14. `graphrag/query/global_search.py` — Global search:
    - Map: for each ACL-filtered community report, LLM "answer in one sentence" → filter NO_INFO
    - Reduce: LLM "synthesise answers"
    - Optimization: cosine pre-filter reports (threshold 0.5)
15. `graphrag/query/drift.py` — DRIFT search:
    - Global phase → extract top-3 entities from reports → Local for each → merge with 0.5 decay
16. `graphrag/query/evidence.py` — GraphEvidenceBundle: extends EvidenceBundle with entities, relationships, community reports, confidence, coverage

### Phase T — Query Router
**Impact: Intelligent routing to the right retrieval mode**
**Files: ~3 | Lines: ~350**

17. `graphrag/router/rules.py` — YAML pattern database (global_patterns, local_patterns, drift_patterns, basic_patterns), compiled regex, case-insensitive
18. `graphrag/router/classifier.py` — BERT classifier interface (distilbert, 4 classes, confidence threshold 0.7, fallback to BASIC_RAG)
19. `graphrag/router/router.py` — 3-stage pipeline:
    - Stage 1: rule_based_route()
    - Stage 2: bert_route() if stage 1 returns None
    - Stage 3: maybe_expand() — BASIC→LOCAL if confidence <0.62, LOCAL→DRIFT if coverage <0.45

### Phase U — Caching + Fusion Extension
**Impact: Performance + integration with existing output layer**
**Files: ~3 | Lines: ~300**

20. `graphrag/cache.py` — Redis cache:
    - Key schemas: graphrag:{mode}:{entity/corpus}:{user_hash}:{query_hash}
    - TTL: Global=3600s, Local/DRIFT=300s
    - Invalidation: delete global keys on community report change
    - Cache warming: top-10 query templates after nightly rebuild
21. `graphrag/fusion.py` — Extend existing fusion:
    - Normalize graph evidence to same format as vector/keyword evidence
    - Cross-encoder rerank on merged set
    - Citation mapping from graph chunks to canonical corpus
22. Update `output/retrieval/hybrid.py` — Add graph mode to fallback matrix

### Phase V — API + Observability
**Impact: User-facing endpoints + operational visibility**
**Files: ~3 | Lines: ~350**

23. `api/routes/graphrag.py` — 4 endpoints:
    - POST /graphrag/query/local
    - POST /graphrag/query/global
    - POST /graphrag/query/drift
    - POST /graphrag/query/route (returns mode + confidence)
    - All ACL-enforced, X-Cache-Status + X-Mode-Used headers
24. `graphrag/metrics.py` — 8 Prometheus metrics:
    - graphrag_query_latency_seconds (by mode, route_decision, cache_hit)
    - graphrag_retrieval_confidence (gauge)
    - graphrag_retrieval_coverage (gauge)
    - graphrag_router_fallback_total (counter)
    - graphrag_cache_hit_total (counter)
    - graphrag_community_update_duration_seconds (histogram)
    - graphrag_llm_tokens_total (counter)
    - graphrag_stale_communities_count (gauge)
25. Wire routes + startup into app.py

---

## Rollout Plan (from spec)

| Phase | Deliverable | Maps To |
|-------|------------|---------|
| 0 | Offline backfill (entity resolution, ACL inheritance) | P + Q |
| 1 | Incremental community updates + ACL filtering + Local mode | R + S(local) |
| 2 | Local search with caching + observability | S(local) + U + V |
| 3 | Query router (rules + BERT + fallbacks) | T |
| 4 | Global search (with corpus snapshot caching) | S(global) + U |
| 5 | DRIFT search (reuses Local/Global) | S(drift) |

### Build order:

```
P → Q → R → S(local) → T → U → S(global) → S(drift) → V
```

---

## Dependencies (new packages)

```toml
[project.optional-dependencies]
graphrag = [
  "neo4j>=5.0",              # Graph database driver
  "networkx>=3.0",           # In-memory graph fallback
  "cdlib>=0.4",              # Leiden community detection
  "spacy>=3.7",              # Entity extraction (NER)
  "hdbscan>=0.8",            # Entity resolution clustering
  "sentence-transformers>=2.5", # Entity embedding (already in output-core)
]
```

---

## Estimated Scope

| Phase | Focus | Files | Lines (est) |
|-------|-------|-------|-------------|
| P | Graph store + schema + models | 4 | ~350 |
| Q | Projection service (entity, resolution, relationships, community, reports) | 6 | ~700 |
| R | Incremental community updates | 2 | ~250 |
| S | Query service (Local, Global, DRIFT) | 4 | ~500 |
| T | Query router (rules, BERT, 3-stage) | 3 | ~350 |
| U | Caching + fusion extension | 3 | ~300 |
| V | API + observability | 3 | ~350 |
| **Total** | | **~25** | **~2,800** |

---

## Combined Platform After GraphRAG

```
Intake Gate (A–G):    33 files,  2,840 lines  ✅
Output Layer (H–O):   22 files,  1,990 lines  ✅
Wiring:               11 files,  1,018 lines  ✅
GraphRAG (P–V):       25 files, ~2,800 lines  ← planned
────────────────────────────────────────────────
Total:               ~91 files, ~8,650 lines
```

---

## Key Architectural Decisions

1. **Neo4j with networkx fallback** — same pattern as Qdrant/ES (production store + in-memory fallback for dev/testing)
2. **Graph is a sidecar, not a replacement** — existing vector/keyword RAG stays unchanged, graph adds entity-relationship reasoning on top
3. **ACL union logic** — entities spanning multiple documents get the union of all source ACL principals (most permissive for that entity)
4. **Incremental over full rebuild** — 5-minute reconciliation for communities with >20% stale chunks, nightly full fallback
5. **Router defaults to BASIC_RAG** — graph modes are opt-in based on query classification, never forced
6. **Community reports are versioned** — old reports kept 7 days for audit, latest always served
7. **EvidenceBundle is extended, not replaced** — graph evidence normalizes to the same structure used by the existing output layer, so fusion + reranking reuse existing code

---

Awaiting approval to proceed.
