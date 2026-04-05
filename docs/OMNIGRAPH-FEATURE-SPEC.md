# OmniGraph — Feature Specification

**Date:** 2026-04-05
**Context:** Deep research across Microsoft GraphRAG, Neo4j GraphRAG, LangChain KG+RAG, LlamaIndex PropertyGraphIndex, NebulaGraph, and the original arXiv paper (2404.16130)
**Purpose:** Define what OmniRAG's dedicated graph engine ("OmniGraph") should have

---

## The Problem OmniGraph Solves

Vector-only RAG finds **similar text** but misses **relationships, structure, and corpus-wide themes**.

- "What are the main risks across all documents?" → vector RAG fails (no corpus-level reasoning)
- "How is Entity A connected to Entity B?" → vector RAG returns isolated chunks, not relationship paths
- "What does Department X's policy say about Topic Y?" → vector RAG may find the chunk but loses the organizational context

OmniGraph adds **entity-relationship reasoning** and **corpus-level synthesis** on top of OmniRAG's existing vector+keyword hybrid retrieval.

---

## Feature List (from deep research)

### 1. LLM-Powered Entity Extraction
**Source: Microsoft GraphRAG, LangChain LLMGraphTransformer**

| Feature | Description |
|---------|-------------|
| Prompted extraction | LLM extracts entities with: name, type, description |
| Entity types | PERSON, ORG, PRODUCT, PROJECT, LOCATION, EVENT, CONCEPT, REGULATORY_TERM |
| Context window | Feed chunk + surrounding context (prev/next chunk) for coreference |
| Confidence scoring | LLM rates extraction confidence (0–1) |
| Batch processing | Process chunks in batches (configurable batch size) |
| Multi-model support | Works with: OpenAI, Ollama (local), Anthropic, any OpenAI-compatible |
| Fallback chain | LLM → spaCy NER → regex patterns (3 tiers, like community reports) |
| Schema-guided mode | Optional: define allowed entity types + relationship types (LlamaIndex approach) |
| Free-form mode | LLM infers types from content (Microsoft approach) |

### 2. LLM-Powered Relationship Extraction
**Source: Microsoft GraphRAG, LangChain**

| Feature | Description |
|---------|-------------|
| Prompted extraction | LLM extracts relationships with: source, target, type, description, weight |
| Relationship types | USES, DEPENDS_ON, INTEGRATES_WITH, SUPPORTS, CONTRADICTS, REGULATES, REPORTS_TO, PRODUCES, CONSUMES |
| Co-occurrence fallback | When LLM unavailable: weight by chunk proximity (existing) |
| Description summarization | Multiple extractions of same relationship → LLM merges descriptions (Microsoft approach) |
| Bidirectional detection | LLM understands "A uses B" and "B is used by A" are the same relationship |
| Cross-chunk relationships | Sliding window (3 chunks) to detect relationships spanning chunk boundaries |

### 3. Entity Resolution (Deduplication)
**Source: Microsoft GraphRAG, our HDBSCAN approach**

| Feature | Description |
|---------|-------------|
| Embedding clustering | Embed entity name + context → HDBSCAN → canonical name (existing) |
| LLM verification | Optional: "Are 'Microsoft', 'MSFT', 'Microsoft Corp' the same entity?" → LLM confirms |
| Alias tracking | Maintain surface_form → resolved_id Redis map (existing) |
| External KB linkage | Optional: query Wikidata SPARQL for canonical entity ID |
| Incremental resolution | New entities resolve against existing graph, not just current batch |

### 4. Hierarchical Community Detection
**Source: Microsoft GraphRAG (Leiden), all platforms**

| Feature | Description |
|---------|-------------|
| Leiden algorithm | Recursive community detection with configurable resolution |
| Multi-level hierarchy | Level 0 (coarse, few large communities) → Level N (fine, many small) |
| Incremental updates | Existing: staleness tracking, >20% stale → recompute |
| Community metadata | Size, density, top entities, key relationships, ACL principals |
| Parent-child links | Community hierarchy for drill-down navigation |

### 5. LLM Community Reports
**Source: Microsoft GraphRAG (core innovation)**

| Feature | Description |
|---------|-------------|
| Per-community summary | LLM generates 300-word report: theme, key entities, relationships, risks |
| Multi-level reports | Reports at each hierarchy level (coarse → detailed) |
| 3-tier fallback | LLM → local model → template (existing) |
| Report versioning | Old reports kept 7 days, latest always served |
| Embedding | Each report embedded for cosine pre-filtering in Global search |
| Incremental regeneration | Only regenerate reports for changed communities |

### 6. Five Query Modes
**Source: Microsoft (Local/Global/DRIFT), LangChain (hybrid), LlamaIndex (property graph)**

| Mode | What it does | When to use |
|------|-------------|-------------|
| **Basic RAG** | Existing vector + keyword hybrid | Simple factoid questions |
| **Local** | Entity-centric graph traversal + linked chunks | Questions about specific entities/relationships |
| **Global** | Map-reduce over community reports | Corpus-wide themes, summaries, risks |
| **DRIFT** | Global primer → extract entities → local refinement | Exploratory, "connect the dots" questions |
| **Hybrid Graph+Vector** | Graph traversal results + vector similarity results → RRF fusion | Best of both worlds — structured + semantic |

### 7. Intelligent Query Router (3-stage)
**Source: Our design, no one else has this**

| Stage | Method | Fallback |
|-------|--------|----------|
| 1 | YAML regex patterns (configurable) | — |
| 2 | BERT classifier (4 classes) | Keyword heuristics |
| 3 | Dynamic override: BASIC→LOCAL (confidence <0.62), LOCAL→DRIFT (coverage <0.45) | — |

### 8. Graph-Aware Context Building
**Source: Microsoft LocalSearchMixedContext, LangChain structured retriever**

| Feature | Description |
|---------|-------------|
| Entity neighborhood | Traverse N hops from matched entities, collect all linked chunks |
| Relationship context | Include relationship descriptions in LLM context (not just entities) |
| Community context | For Global: include community reports ranked by relevance |
| Source traceability | Every piece of context links back to original chunk → document → source |
| Context budget | Prioritize and filter candidates to fit within LLM context window |
| Conversation history | Use previous turns to refine entity extraction from query |

### 9. Graph Store Abstraction
**Source: LlamaIndex (multi-store), Neo4j, our design**

| Store | Use case |
|-------|----------|
| Neo4j | Production: Cypher queries, native graph, vector + full-text built-in |
| NetworkX | Development: in-memory, zero dependencies |
| PostgreSQL + pgvector | Alternative: graph-as-tables for teams that don't want Neo4j |

### 10. ACL-Aware Graph
**Source: Our design (unique — no other platform has this)**

| Feature | Description |
|---------|-------------|
| Per-node ACL | Every entity, chunk, community, report carries acl_principals |
| Union semantics | Entity in multiple docs → ACL = union of all doc ACLs |
| Query-time filtering | All traversals include ACL WHERE clause |
| Permission revocation | Reconciliation detects ACL changes → re-index affected subgraph |

### 11. Caching
**Source: Our design**

| Mode | TTL | Invalidation |
|------|-----|-------------|
| Global | 1 hour | On community report change |
| Local/DRIFT | 5 minutes | TTL-based |
| Report embeddings | Persistent | On report regeneration |

### 12. Observability
**Source: Our design + Microsoft's approach**

| Metric | What |
|--------|------|
| Query latency by mode | p50, p95, p99 per mode |
| Confidence + coverage | Per query result quality |
| Router decisions | Rule-based vs BERT vs dynamic override rates |
| Cache hit ratio | Per mode |
| Community staleness | Stale community backlog count |
| LLM token usage | Per operation (extraction, report gen, global map/reduce) |
| Entity/relationship counts | Graph growth over time |
| Extraction quality | Confidence distribution of extracted entities |

### 13. Graph Explorer UI
**Source: Unique to OmniRAG**

| Feature | Description |
|---------|-------------|
| Entity search | Search by name, type, or description |
| Neighborhood view | Show entity + N-hop neighbors as list |
| Community browser | Browse community hierarchy, read reports |
| Relationship explorer | See all relationships for an entity |
| Ingestion status | Entities/relationships/communities counts, last indexing time |
| Quality comparison | Run same query in Basic vs Local vs Global, compare results |

### 14. Extraction Modes (User Choice)
**Source: Our design**

| Mode | Entity Extraction | Cost | Quality |
|------|------------------|------|---------|
| **Regex** | spaCy + patterns | Free | Basic (existing) |
| **LLM** | Prompted GPT-4/Ollama | $$$ or free | High (Microsoft-level) |
| **Schema** | LLM with type constraints | $$$ or free | High + controlled |
| **Hybrid** | LLM for important docs, regex for bulk | $$ | Balanced |

---

## What Makes OmniGraph Unique (vs Competition)

| Feature | Microsoft GraphRAG | LangChain KG | LlamaIndex PG | Neo4j GraphRAG | **OmniGraph** |
|---------|-------------------|-------------|---------------|---------------|--------------|
| LLM extraction | ✅ | ✅ | ✅ | ✅ | ✅ |
| Community detection | ✅ Leiden | ❌ | ❌ | ❌ | ✅ Leiden |
| Community reports | ✅ | ❌ | ❌ | ❌ | ✅ (3-tier) |
| Global search (map-reduce) | ✅ | ❌ | ❌ | ❌ | ✅ |
| DRIFT search | ✅ | ❌ | ❌ | ❌ | ✅ |
| Query router | ❌ | ❌ | ❌ | ❌ | ✅ (3-stage) |
| ACL per node | ❌ | ❌ | ❌ | ❌ | ✅ |
| Backpressure | ❌ | ❌ | ❌ | ❌ | ✅ |
| Schema-guided extraction | ❌ | ❌ | ✅ | ❌ | ✅ |
| Free-form extraction | ✅ | ✅ | ✅ | ✅ | ✅ |
| Regex/NER fallback | ❌ (LLM-only) | ❌ | ❌ | ❌ | ✅ |
| Multi-store (Neo4j/PG/memory) | ❌ (Parquet) | ❌ (Neo4j only) | ✅ | ✅ (Neo4j only) | ✅ |
| Governed intake | ❌ | ❌ | ❌ | ❌ | ✅ (12-state) |
| Hybrid vector+graph retrieval | ❌ | ✅ | ✅ | ✅ | ✅ |
| Cost transparency | ❌ | ❌ | ❌ | ❌ | ✅ |
| Works offline (no LLM) | ❌ | ❌ | ❌ | ❌ | ✅ (regex mode) |
| Built-in UI | ❌ | ❌ | ❌ | ❌ | ✅ |

**OmniGraph is the only system that combines ALL of these.** Microsoft has the best extraction quality but no governance, no ACL, no router, no offline mode. LangChain/LlamaIndex have graph support but no communities, no Global/DRIFT, no reports. Neo4j has the store but not the pipeline.

---

## Implementation Priority

```
P0: LLM-powered extraction (the quality upgrade)
P1: Description summarization + improved resolution
P2: Multi-level community reports with embeddings
P3: DRIFT search upgrade (using community report embeddings for primer)
P4: Schema-guided extraction mode
P5: Graph Explorer UI enhancements
P6: Hybrid Graph+Vector fusion mode
P7: Cost tracking + transparency
```

---

## Estimated Scope

| Priority | What | Files | Lines |
|----------|------|-------|-------|
| P0 | LLM extraction prompts + 3-tier fallback | 2 | ~400 |
| P1 | Description summarization + resolution upgrade | 2 | ~300 |
| P2 | Multi-level reports + embeddings | 2 | ~250 |
| P3 | DRIFT upgrade with report embeddings | 1 | ~150 |
| P4 | Schema-guided extraction | 1 | ~200 |
| P5 | Graph Explorer UI | 1 | ~300 |
| P6 | Hybrid Graph+Vector fusion | 1 | ~200 |
| P7 | Cost tracking | 1 | ~150 |
| **Total** | | **~11** | **~1,950** |

This upgrades the existing GraphRAG code — no new packages, no Microsoft dependency, same architecture, Microsoft-level quality.
