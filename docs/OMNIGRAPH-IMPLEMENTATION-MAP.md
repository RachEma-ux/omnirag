# OmniGraph Implementation Map — Spec Files → OmniRAG Code

**Date:** 2026-04-05
**Input:** 6 OmniGraph spec files from `downloads/omnigraph/`
**Target:** Upgrade existing OmniRAG code — not a rewrite
**Agent:** Planner (no code, mapping only)

---

## Document Inventory

| # | File | What it defines |
|---|------|----------------|
| 1 | Engineering Specification | 14 mandatory features, 12 services, 23 contracts, data model |
| 2 | Technical Specification | Full architecture, service boundaries, API surface, deployment |
| 3 | Implementation Roadmap | 24 weeks, 6 phases, sprint-by-sprint |
| 4 | Implementation Artifacts | Neo4j Cypher DDL, PostgreSQL DDL, Python protocols, JSON payloads |
| 5 | README | Docker Compose, Makefile, .env, dev setup |
| 6 | Downloadable Files | Same as README + ready-to-copy files |

---

## Mapping Strategy

### What we keep (OmniRAG strengths — don't touch)

| OmniRAG Component | Why keep |
|-------------------|----------|
| Intake Gate (A–G) | More advanced than spec's Ingestion Service (12-state vs basic) |
| Backpressure system | Not in spec at all (token bucket, admission, circuit breakers) |
| Port registry (8100–8199) | Already centralized, spec has no port management |
| FastAPI + vanilla JS shell | Working, 4-tab UI, dark theme — spec wants Next.js (overkill) |
| Docker Compose | Already adapted for our port scheme |
| 92 integration tests | Spec has no tests defined |

### What we adopt from spec (upgrades)

| Spec Component | Maps To | What Changes |
|----------------|---------|-------------|
| 20+ canonical data model objects | `intake/models.py` + new models | Add: Extraction, ResolutionCase, QueryPlan, ContextBundle, Answer, AnswerTrace, CacheKey, MetricEvent, AgentRun |
| 23 Python Protocol contracts | New `omnirag/contracts/` package | Define all interfaces as ABC — existing code implements them |
| 12 services architecture | Map onto existing modules | Rename/restructure to match service boundaries |
| LLM extraction (Feature #1, #2) | `graphrag/extraction/entities.py` + `relationships.py` | Add LLM prompts alongside regex |
| Entity resolution LLM verification (Feature #3) | `graphrag/extraction/resolution.py` | Add Ollama "Are these the same?" step |
| Multi-resolution Leiden (Feature #4) | `graphrag/extraction/communities.py` | Run at γ=0.5, 1.0, 2.0 + parent hierarchy |
| Enriched community reports (Feature #5) | `graphrag/extraction/reports.py` | Add key_entities, key_relations, evidence_links, freshness |
| Context Builder (Feature #8) | New `omnirag/graphrag/context.py` | N-hop expansion, relation verbalization, token budgeting |
| AnswerTrace (Feature #12) | New `omnirag/output/tracing.py` | Log every query: plan, context, LLM, tokens, latency, ACL |
| QueryPlan object | `graphrag/router/router.py` | Formalize RouteDecision → QueryPlan with all 3 stage traces |
| CacheKey with ACL fingerprint | `graphrag/cache.py` | Add graph_version, embedding_version, prompt_version |
| 25 routing rules | `graphrag/router/rules.yaml` | Expand from 12 patterns to 25 |
| Dynamic Override conditions | `graphrag/router/router.py` | Add: graph coverage, ACL filter %, token budget, system load, cache redirect |
| PostgreSQL DDL (pgvector + FTS) | `intake/storage/` + `output/storage/` | Merge spec's tables into our existing schemas |
| Neo4j schema (constraints + indexes) | `graphrag/store.py` | Adopt spec's Cypher DDL verbatim |
| PageRank | New `graphrag/algorithms.py` | Add to Graph Intelligence alongside Leiden |

### What we skip (not needed yet)

| Spec Component | Why skip |
|----------------|----------|
| Next.js frontend | We have working vanilla JS shell — rewrite adds no value |
| Chainlit Ops UI | Nice-to-have, not needed for core platform |
| LangGraph workflows | We have custom pipeline — LangGraph adds dependency complexity |
| AutoGen agents | No agentic use case yet |
| MCP (Model Context Protocol) | Tool protocol standard — adopt when we add tools |
| OpenSPG/KAG schema mode | Enterprise ontology — defer until domain-specific deployment |
| Power BI connector | Analytics integration — defer |
| NebulaGraph scale-out | Only needed at >100M nodes |
| Milvus scale-out | Only needed at >10M vectors |

---

## Implementation Plan (10 Phases)

### Phase G1 — Canonical Data Model Upgrade
**Spec ref: Engineering Spec §5, Tech Spec §3**
**Files: ~2 | Lines: ~400**

What changes:
- Add to `intake/models.py` or new `omnirag/models/canonical.py`:
  - `Extraction` — entity/relation candidate with confidence + provenance span
  - `ResolutionCase` — merge decision + confidence + verification trace
  - `QueryPlan` — selected_mode + all 3 router stage traces
  - `ContextBundle` — anchor_entities, selected_relations, path_summaries, supporting_chunks, token_budget_used
  - `Answer` — text + citations + evidence_links
  - `AnswerTrace` — query_plan + context_bundle + llm_model + token_usage + latency + cache_hit + acl_filtered
  - `CacheKey` — mode + query_hash + acl_fingerprint + graph_version + embedding_version + prompt_version
  - `MetricEvent` — name + value + labels + timestamp
- Update existing models to include spec fields (description on Entity/Relation, provenance_span on Extraction, etc.)

### Phase G2 — Service Contracts (23 Protocols)
**Spec ref: Engineering Spec §6, Tech Spec §4, Artifacts §2**
**Files: ~1 | Lines: ~300**

What changes:
- New `omnirag/contracts.py` defining all 23 interfaces as Python ABC/Protocol:
  - Parser, Normalizer, Extractor, EntityResolver, GraphBuilder
  - CommunityBuilder, ReportGenerator, Embedder
  - GraphStore, VectorStore, TextIndex, GraphAlgorithm
  - QueryRouter, RetrievalPlanner, GraphRetriever, VectorRetriever, HybridRetriever
  - ContextBuilder, AuthorizationEngine, CacheManager
  - Reasoner, AnswerSynthesizer, TraceRecorder
- Existing implementations annotated with which contract they fulfill
- No code changes to existing implementations — just interface definitions

### Phase G3 — LLM-Powered Extraction (Features #1, #2, #14)
**Spec ref: Engineering Spec §8.1, Tech Spec §4.2**
**Files: ~3 | Lines: ~500**

What changes:
- `graphrag/extraction/entities.py` — add `LLMEntityExtractor`:
  - Prompt: "Extract ALL entities with name, type, description, confidence"
  - Uses OllamaAdapter or OpenAIAdapter (existing)
  - JSON structured output parsing
  - 3-tier: LLM → spaCy → regex (existing fallback chain)
- `graphrag/extraction/relationships.py` — add `LLMRelationshipExtractor`:
  - Prompt: "Extract ALL relationships with source, target, type, description, weight"
  - Description summarization: multiple extractions → merge descriptions
  - Cross-chunk sliding window (3 chunks)
- `graphrag/extraction/prompts.py` — all extraction prompt templates:
  - Entity extraction prompt
  - Relationship extraction prompt
  - Entity verification prompt ("Are these the same?")
  - Community report prompt (upgrade existing)
- Extraction mode selector based on `extraction_mode` config (regex/llm/schema/hybrid)

### Phase G4 — Entity Resolution Upgrade (Feature #3)
**Spec ref: Engineering Spec §8.2, Tech Spec §4.3**
**Files: ~1 | Lines: ~200**

What changes:
- `graphrag/extraction/resolution.py`:
  - Add blocking step before HDBSCAN: exact name, normalized name, embedding similarity >0.85
  - Add LLM verification for borderline clusters (confidence 0.4–0.7): Ollama "Are these the same entity?"
  - Add `ResolutionCase` output: merge_decision, confidence, verification_trace
  - Incremental resolution: new entities resolve against existing graph entities

### Phase G5 — Multi-Resolution Leiden + PageRank (Feature #4)
**Spec ref: Engineering Spec §8.3, Tech Spec §4.5**
**Files: ~2 | Lines: ~250**

What changes:
- `graphrag/extraction/communities.py`:
  - Run Leiden at 3 resolutions: γ=0.5 (broad), γ=1.0 (medium), γ=2.0 (fine)
  - Build parent-child hierarchy: level 0 → level 1 → level 2
  - Store `parent_community_id` on each community
  - Membership table: entity → community at each level
- New `graphrag/algorithms.py`:
  - PageRank computation (NetworkX or Neo4j GDS)
  - Store scores on entities → used for context budget prioritization

### Phase G6 — Context Builder (Feature #8)
**Spec ref: Engineering Spec §8.7, Tech Spec §4.9**
**Files: ~1 | Lines: ~300**

What changes:
- New `graphrag/context.py` — `ContextBuilder`:
  - Input: RetrievalResult (subgraph + chunks + communities)
  - Step 1: Expand from anchor entities (N-hop, default 2)
  - Step 2: Verbalize relations: "{source} {type} {target}: {description}"
  - Step 3: Attach top-k chunks (by cosine score >0.7)
  - Step 4: Add community summaries (for Global mode)
  - Step 5: Apply token budget (default 2048): greedy selection by importance (PageRank for entities, recency for chunks)
  - Output: `ContextBundle` with explicit evidence links
  - Deduplication: remove overlapping chunks, duplicate entity descriptions

### Phase G7 — Answer Tracing (Feature #12)
**Spec ref: Engineering Spec §8.11, Tech Spec §4, Artifacts §1.2**
**Files: ~2 | Lines: ~250**

What changes:
- New `omnirag/output/tracing.py` — `TraceRecorder`:
  - Record every query: QueryPlan + ContextBundle + LLM model + token usage + latency + cache hit + ACL filtered nodes
  - Store in PostgreSQL `query_traces` table
  - API: `GET /v1/traces/{id}` returns full AnswerTrace
  - API: `GET /v1/traces` lists recent traces with filters
- Update search + graphrag endpoints to create traces on every query
- Add `AnswerTrace` to query responses (optional, via `?trace=true`)

### Phase G8 — Enhanced Router (25 Rules + Dynamic Override)
**Spec ref: Engineering Spec §8.6, Tech Spec §4.7**
**Files: ~2 | Lines: ~200**

What changes:
- `graphrag/router/rules.yaml` — expand to 25 rules (spec provides examples)
- `graphrag/router/router.py` — upgrade Stage 3 (Dynamic Override):
  - Add conditions: graph coverage <0.1 → BASIC, ACL filtered >50% → HYBRID, token budget <512 → BASIC, system load >0.7 → BASIC, cache hit for other mode → redirect
  - Optional: lightweight LLM override (Ollama 3B with few-shot examples)

### Phase G9 — Cache Key Upgrade + Report Enrichment
**Spec ref: Engineering Spec §8.10, §8.4, Tech Spec §4.6**
**Files: ~2 | Lines: ~200**

What changes:
- `graphrag/cache.py`:
  - Cache key format: `{mode}:{query_hash}:{acl_fingerprint}:{graph_version}:{embedding_version}:{prompt_version}`
  - Add graph_version tracking (incremented on every graph write)
  - Add prompt_version tracking (incremented on prompt template change)
  - TTL per mode: Basic=15m, Local=10m, Global=60m, DRIFT=5m, Hybrid=10m
  - Invalidation: add source re-ingested, extraction rerun, entity merge, ACL change triggers
- `graphrag/extraction/reports.py`:
  - Enrich CommunityReport: add `key_entities`, `key_relations`, `evidence_links`, `freshness_timestamp`, `model_version`
  - Embed each report for cosine pre-filtering in Global search

### Phase G10 — PostgreSQL Schema Merge + Neo4j DDL
**Spec ref: Artifacts §1.1, §1.2**
**Files: ~2 | Lines: ~200**

What changes:
- `intake/storage/schema.sql` — add spec's tables:
  - `entity_search` (FTS on entity names + aliases)
  - `ingestion_jobs` (already have `sync_jobs` — merge)
  - `graph_build_jobs` (new)
  - `community_runs` (new)
  - `query_traces` (new)
  - `node_acls` (already have `acl_snapshots` — merge)
  - `cache_invalidation_log` (new)
  - `metric_events` (new)
  - `evaluations` (new — LLM judge scores)
- `graphrag/store.py` — adopt spec's Neo4j Cypher DDL:
  - Constraints: entity_id, relation_id, community_id unique
  - Indexes: entity_name, entity_type, entity_acl, relation_type, relation_acl, community_level
  - BELONGS_TO edges (entity → community)
  - PARENT_OF edges (community hierarchy)

---

## File-by-File Mapping

| Spec Service (12) | OmniRAG Existing File | Changes |
|-------------------|----------------------|---------|
| 1. Ingestion Service | `intake/gate.py` (12-state) | Keep — ours is superior |
| 2. Extraction Service | `graphrag/extraction/entities.py`, `relationships.py` | Add LLM mode (G3) |
| 3. Entity Resolution | `graphrag/extraction/resolution.py` | Add LLM verification (G4) |
| 4. Graph Build Service | `graphrag/store.py` + `projection.py` | Adopt Neo4j DDL (G10) |
| 5. Graph Intelligence | `graphrag/extraction/communities.py` | Multi-resolution + PageRank (G5) |
| 6. Community Report | `graphrag/extraction/reports.py` | Enrich fields (G9) |
| 7. Query Router | `graphrag/router/router.py` | 25 rules + enhanced override (G8) |
| 8. Retrieval Service | `output/retrieval/hybrid.py` + `graphrag/query/*.py` | Add ContextBuilder (G6) |
| 9. Context Builder | **New**: `graphrag/context.py` | Full implementation (G6) |
| 10. Authorization Engine | `intake/acl/manager.py` | Already implemented |
| 11. Reasoning Service | `output/generation/engine.py` | Add tracing (G7) |
| 12. Workflow Runtime | **Skip** | LangGraph deferred |
| Cache Manager | `graphrag/cache.py` | Enhanced keys (G9) |
| Control Plane | `output/metrics.py` + `graphrag/metrics.py` | Add MetricEvent storage (G7) |

---

## Estimated Scope

| Phase | Focus | Files | Lines |
|-------|-------|-------|-------|
| G1 | Canonical data model (10+ new objects) | 2 | ~400 |
| G2 | 23 service contracts (ABC/Protocol) | 1 | ~300 |
| G3 | LLM extraction (entities + relationships + prompts) | 3 | ~500 |
| G4 | Entity resolution upgrade (blocking + LLM verify) | 1 | ~200 |
| G5 | Multi-resolution Leiden + PageRank | 2 | ~250 |
| G6 | Context Builder (N-hop + verbalize + budget) | 1 | ~300 |
| G7 | Answer tracing (QueryTrace + API) | 2 | ~250 |
| G8 | Router upgrade (25 rules + dynamic conditions) | 2 | ~200 |
| G9 | Cache key upgrade + report enrichment | 2 | ~200 |
| G10 | PostgreSQL + Neo4j schema merge | 2 | ~200 |
| **Total** | | **~18** | **~2,800** |

---

## Build Order

```
G1 (data model)  → G2 (contracts)  → G3 (LLM extraction)
                                         ↓
                    G4 (resolution)  →  G5 (communities + PageRank)
                                         ↓
                    G6 (context builder)  →  G7 (tracing)
                                              ↓
                    G8 (router)  →  G9 (cache + reports)  →  G10 (schema)
```

G1 and G2 are foundations. G3 is the quality upgrade. Everything else builds on those.

---

## After Implementation

```
Existing OmniRAG:   ~100 files,  ~9,150 lines  ✅
OmniGraph upgrade:   ~18 files,  ~2,800 lines  ← planned
───────────────────────────────────────────────────
Total:             ~118 files, ~11,950 lines
```

The platform will implement **all 14 mandatory features** from the Engineering Specification, with every service mapped to a concrete file, every contract defined as a Python protocol, and every data model formalized.

---

Awaiting approval to proceed.
