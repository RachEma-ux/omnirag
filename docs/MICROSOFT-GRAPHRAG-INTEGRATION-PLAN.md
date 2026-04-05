# Microsoft GraphRAG Integration into OmniRAG — Execution Plan

**Date:** 2026-04-05
**Source:** microsoft/graphrag v3.0.8 (PyPI), MIT license
**Target:** OmniRAG `GraphRAG` tab
**Agent:** Planner (report only, no code)

---

## What Microsoft GraphRAG Is

A **data pipeline + query engine** from Microsoft Research that:

1. **Indexes** documents → extracts entities + relationships → detects communities (Leiden) → generates LLM community reports → embeds into vector store → outputs **Parquet files**
2. **Queries** via 3 modes: Local (entity-centric), Global (map-reduce over community reports), DRIFT (hybrid)
3. **CLI**: `graphrag init`, `graphrag index`, `graphrag query`
4. **Python API**: programmatic indexing + search classes
5. **Requires**: Python 3.11–3.13, LLM API key (OpenAI or Azure OpenAI)

### What it produces (Parquet files):
- `entities.parquet` — extracted entities with descriptions
- `relationships.parquet` — entity pairs with descriptions + weights
- `communities.parquet` — Leiden community assignments
- `community_reports.parquet` — LLM-generated summaries
- `text_units.parquet` — source text chunks
- `documents.parquet` — source document metadata
- Embeddings written to configured vector store

---

## Current State: OmniRAG's Custom GraphRAG vs Microsoft's

| Feature | OmniRAG Custom (current) | Microsoft GraphRAG |
|---------|------------------------|-------------------|
| Entity extraction | spaCy NER + regex fallback | LLM-based (GPT-4 prompted extraction) |
| Entity resolution | HDBSCAN clustering | LLM-based deduplication |
| Relationship extraction | Co-occurrence weighting | LLM-based (prompted pair extraction) |
| Community detection | Leiden (cdlib) | Leiden (graspologic/networkx) |
| Community reports | 3-tier (LLM → local → template) | LLM-only (GPT-4 summarization) |
| Local search | Custom Cypher traversal | Microsoft's LocalSearch class |
| Global search | Custom map-reduce | Microsoft's GlobalSearch class |
| DRIFT search | Custom 2-phase | Microsoft's DRIFTSearch class |
| Query router | 3-stage (rules → BERT → dynamic) | Not included (user chooses mode) |
| Storage | Neo4j + networkx | Parquet files + vector store |
| Graph store | Neo4j (networkx fallback) | NetworkX in-memory from Parquet |
| Quality | Basic NER (regex) | LLM-powered (much higher quality) |
| Cost | Free (no LLM for extraction) | Expensive (LLM for every step) |

### Key insight:
Microsoft's extraction quality is **far superior** (LLM-powered vs regex), but their system is **expensive** and **LLM-dependent**. The integration should use Microsoft's pipeline for indexing (quality) while keeping OmniRAG's infrastructure for serving (governance, ACL, backpressure, UI).

---

## Integration Architecture

```
OmniRAG Intake Gate                Microsoft GraphRAG
─────────────────                  ───────────────────
Source → Connector → Extractor     graphrag.index()
       → Materializer → Chunks         ↓
              ↓                    Parquet files:
         OmniRAG Chunks ──────→   entities, relationships,
              ↓                    communities, reports
         GraphRAG Tab                   ↓
              ↓                    graphrag.query()
    ┌─────────┴──────────┐        LocalSearch / GlobalSearch / DRIFTSearch
    │                    │              ↓
  OmniRAG custom      Microsoft    Merged results
  (free, fast,        (LLM-powered,     ↓
   lower quality)      expensive,   OmniRAG delivery
                       high quality)  (REST, WS, export)
```

### Two modes in the GraphRAG tab:

1. **OmniRAG mode** (current) — free, uses spaCy/regex, fast, works offline
2. **Microsoft mode** (new) — uses `graphrag` package, LLM-powered, high quality, requires API key

User picks which mode per query. Or auto-route based on query complexity.

---

## Execution Plan (5 Phases)

### Phase X1 — Install + Initialize Microsoft GraphRAG
**Files: ~2 | Lines: ~200**

1. Add `graphrag>=3.0` to optional dependencies in `pyproject.toml`
2. `graphrag/microsoft/__init__.py` — wrapper module
3. `graphrag/microsoft/config.py` — Configuration manager:
   - Read API key from env (`GRAPHRAG_API_KEY`) or adapter settings
   - Generate `settings.yaml` programmatically (not via CLI)
   - Configure: LLM provider (openai/azure), model, temperature
   - Configure: embedding model, chunk size, community detection params
   - Support both OpenAI and Ollama (via OpenAI-compatible endpoint)

### Phase X2 — Indexing Integration
**Files: ~3 | Lines: ~350**

4. `graphrag/microsoft/indexer.py` — Indexing bridge:
   - Takes OmniRAG `CanonicalDocument` + `Chunk` objects
   - Writes them to `input/` folder as text files (Microsoft's expected format)
   - Calls `graphrag index` programmatically (Python API, not CLI)
   - Reads output Parquet files → converts to OmniRAG models:
     - `entities.parquet` → `GraphEntity`
     - `relationships.parquet` → `GraphRelationship`
     - `communities.parquet` → `GraphCommunity`
     - `community_reports.parquet` → `CommunityReport`
   - Stores in OmniRAG's graph store (Neo4j or networkx)
   - Tracks indexing status: pending → running → complete → failed

5. `graphrag/microsoft/parquet_loader.py` — Parquet reader:
   - Read all 6 output tables
   - Map columns to OmniRAG models
   - Handle schema differences between graphrag versions

6. Wire into intake gate:
   - After CHUNKED state: optionally trigger Microsoft GraphRAG indexing
   - Config flag: `GRAPHRAG_MICROSOFT_ENABLED=true`
   - Run async (background task) since indexing is expensive

### Phase X3 — Query Integration
**Files: ~3 | Lines: ~400**

7. `graphrag/microsoft/search.py` — Search bridge:
   - Load Parquet data into Microsoft's search classes
   - `microsoft_local_search(query, entities, relationships, text_units)`
   - `microsoft_global_search(query, community_reports)`
   - `microsoft_drift_search(query, ...)`
   - Convert Microsoft's response format → OmniRAG `GraphEvidenceBundle`
   - Handle: LLM errors, timeouts, empty results

8. `graphrag/microsoft/context.py` — Context builder:
   - Build context from OmniRAG's graph store data
   - Or from Parquet files directly
   - Feed into Microsoft's LocalSearchMixedContext / GlobalCommunityContext

9. Update `api/routes/graphrag.py`:
   - Add `engine` parameter: `"omnirag"` (default) or `"microsoft"`
   - Each endpoint gets: `/graphrag/query/local?engine=microsoft`
   - Auto-detect: if Microsoft index exists, offer it; otherwise fallback to OmniRAG

### Phase X4 — GraphRAG Tab UI
**Files: ~1 | Lines: ~200**

10. Update `app.js` GraphRAG tab:
    - **Engine selector**: toggle between "OmniRAG" and "Microsoft" modes
    - **Index status**: show if Microsoft index exists, when last built, entity/relationship counts
    - **Build Index button**: triggers Microsoft indexing on current intake data
    - **Query with engine**: shows which engine answered, latency, quality comparison
    - **Cost warning**: display estimated token usage before Microsoft indexing
    - **Settings**: API key input, model selection, provider (OpenAI/Azure/Ollama)

### Phase X5 — Hybrid Mode + Quality Comparison
**Files: ~2 | Lines: ~250**

11. `graphrag/microsoft/hybrid.py` — Hybrid query:
    - Run same query through both engines
    - Merge results (union of entities, relationships, chunks)
    - Compare: confidence, coverage, entity count, answer quality
    - Return best answer or merged answer with dual citations

12. `graphrag/microsoft/benchmark.py` — Quality benchmark:
    - Run N queries through both engines
    - Compare: entities found, relationships extracted, answer relevance
    - Output: comparison report showing quality delta
    - Helps user decide if Microsoft's LLM cost is worth the quality gain

---

## API Changes

### New query parameter:

```
POST /graphrag/query/local
{
  "query": "...",
  "user_principal": "...",
  "engine": "omnirag" | "microsoft" | "hybrid"
}
```

### New endpoints:

```
POST /graphrag/microsoft/index      — trigger Microsoft indexing
GET  /graphrag/microsoft/status     — indexing status + stats
POST /graphrag/microsoft/configure  — set API key + model
GET  /graphrag/microsoft/compare    — quality comparison report
```

---

## Dependencies

```toml
[project.optional-dependencies]
microsoft-graphrag = [
  "graphrag>=3.0",          # Microsoft GraphRAG package
  "pyarrow>=15.0",          # Parquet file reading
]
```

Note: `graphrag` pulls in many dependencies (openai, tiktoken, graspologic, networkx, datashaper, etc.). It's a heavy package (~200MB with deps). Keep it optional.

---

## Estimated Scope

| Phase | Focus | Files | Lines |
|-------|-------|-------|-------|
| X1 | Install + config | 2 | ~200 |
| X2 | Indexing bridge | 3 | ~350 |
| X3 | Query bridge | 3 | ~400 |
| X4 | Tab UI | 1 | ~200 |
| X5 | Hybrid + benchmark | 2 | ~250 |
| **Total** | | **~11** | **~1,400** |

---

## Key Decisions

1. **Microsoft is optional, not required.** OmniRAG works without it. The `graphrag` package is only imported when `engine=microsoft` is used.

2. **OmniRAG stays the serving layer.** Microsoft's indexing produces Parquet → OmniRAG loads into its graph store → OmniRAG serves via its ACL-filtered, cached, observable query layer.

3. **No CLI dependency.** We use Microsoft's Python API, not `graphrag init`/`graphrag index` CLI. This avoids subprocess management and gives us control over the pipeline.

4. **Dual engine, not replacement.** User can run both and compare. Some queries are better with OmniRAG (fast, free), others with Microsoft (deep, expensive).

5. **Cost transparency.** Before running Microsoft indexing, show estimated token count and cost. GraphRAG indexing on 100 pages can cost $5-50 in LLM tokens.

6. **Ollama support.** Configure Microsoft GraphRAG to use Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`) instead of OpenAI. Free local LLM indexing.

---

## After Integration

```
OmniRAG GraphRAG Tab
────────────────────
[ Engine: OmniRAG ▾ | Microsoft ▾ | Hybrid ▾ ]

Query: [________________________] [Search]

  ┌─ OmniRAG (free, instant) ──────────────────┐
  │ Entities: 12 | Relationships: 8             │
  │ Answer: ...                                  │
  │ Confidence: 0.72 | Coverage: 0.45           │
  └─────────────────────────────────────────────┘

  ┌─ Microsoft (LLM, 2.3s, ~$0.02) ────────────┐
  │ Entities: 34 | Relationships: 52            │
  │ Answer: ... (more detailed, with citations)  │
  │ Confidence: 0.91 | Coverage: 0.82           │
  └─────────────────────────────────────────────┘

Index Status: ✅ Built 2h ago | 847 entities | 1,203 relationships | 23 communities
[Rebuild Index] [Compare Engines] [Settings]
```

---

Awaiting approval to proceed.
