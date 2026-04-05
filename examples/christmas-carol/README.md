# OmniRAG Demo — A Christmas Carol (End-to-End)

This example demonstrates the **full OmniRAG pipeline** from raw text to interactive knowledge graph visualization, using Charles Dickens' "A Christmas Carol" from Project Gutenberg.

---

## What This Demo Shows

```
Raw Text → Intake Gate (12-state) → 71 Chunks → 71 Embeddings →
  → 3 Index Stores (vector + keyword + metadata)
  → Graph Projection: 142 Entities + 1,981 Relationships + 1 Community
  → Knowledge Graph Visualization
  → Search & Query (5 modes)
```

---

## Step-by-Step Guide

### Step 1: Start OmniRAG

```bash
cd ~/omnirag
TMPDIR=/data/data/com.termux/files/usr/tmp omnirag serve --host 127.0.0.1 --port 8100
```

Open http://127.0.0.1:8100/ in your browser.

### Step 2: Download the Sample Text

```bash
curl -sL "https://www.gutenberg.org/cache/epub/24022/pg24022.txt" \
  -o /data/data/com.termux/files/usr/tmp/christmas_carol.txt
```

This downloads "A Christmas Carol" by Charles Dickens (3,976 lines, public domain).

### Step 3: Run the Full Pipeline

```bash
cd ~/omnirag
python3 -m omnirag.demo
```

This runs:

1. **Intake** — ingests the text file through the 12-state pipeline:
   ```
   REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED →
   MATERIALIZED → ENRICHED → ACL_BOUND → CHUNKED → INDEXED →
   VERIFIED → ACTIVE
   ```
   Result: 1 document, 71 chunks

2. **Embedding** — generates vectors for all 71 chunks
   (random vectors without sentence-transformers, real vectors with it)

3. **Indexing** — writes to 3 stores:
   - Vector store (Qdrant or in-memory fallback)
   - Keyword store (Elasticsearch or in-memory fallback)
   - Metadata store (PostgreSQL or in-memory fallback)

4. **Graph Projection** — extracts knowledge graph:
   - 142 entities (Scrooge, Cratchit, Tiny Tim, Christmas spirits...)
   - 1,981 relationships (co-occurrence weighted)
   - 1 community (Leiden detection)
   - 1 community report (3-tier: LLM → local model → template)

### Step 4: Explore in the UI

Open http://127.0.0.1:8100/ and navigate to each tab:

#### RAG Tab
- See the ingested document in the intake section
- Click "View Jobs" to see the job with 71 chunks

#### OmniGraph Tab
- Type "Who is Scrooge?" → click "Auto Route" or "Local"
- See entities and relationships from the knowledge graph
- Check Graph Stats: 142 entities, 1,981 relationships

#### Visualization Tab
- Click "+ Sample" to load demo data, OR the graph loads from the API
- See entities as colored nodes (PERSON=indigo, ORG=green, etc.)
- Drag nodes to rearrange
- Click a node to see its connections
- Switch layouts: Force / Hierarchy / Circular
- Toggle "☰ Filter" to filter by entity type
- Click "🔗 Path" → select two nodes → see shortest path highlighted

#### Chat Tab
- Type "What are the main themes in A Christmas Carol?"
- The system searches the indexed chunks and generates an answer

### Step 5: Try Different Queries

| Query | Expected Mode | What it tests |
|-------|--------------|---------------|
| "Who is Scrooge?" | Basic/Local | Entity lookup |
| "What are the main themes?" | Global | Corpus-wide synthesis |
| "How is Scrooge related to Tiny Tim?" | Local | Relationship traversal |
| "Investigate the transformation of Scrooge" | DRIFT | Exploratory |
| "Compare the three spirits" | Hybrid | Mixed retrieval |

---

## What Gets Created

### Entities (sample of 142)

| Entity | Type | Description |
|--------|------|-------------|
| Ebenezer Scrooge | PERSON | Main character, miserly businessman |
| Bob Cratchit | PERSON | Scrooge's underpaid clerk |
| Tiny Tim | PERSON | Cratchit's disabled son |
| Christmas Past | PERSON | First spirit visiting Scrooge |
| Christmas Present | PERSON | Second spirit |
| Christmas Yet | PERSON | Third spirit (future) |
| Jacob Marley | PERSON | Scrooge's deceased business partner |
| Fred | PERSON | Scrooge's nephew |
| Project Gutenberg | ORG | Source of the text |

### Relationships (sample of 1,981)

Co-occurrence weighted relationships between entities:
- Scrooge ↔ Cratchit (weight: 5.0 — max, frequent co-occurrence)
- Scrooge ↔ Marley (weight: 4.5)
- Scrooge ↔ Christmas Past (weight: 3.0)
- Tiny Tim ↔ Cratchit (weight: 3.5)

### Community

All 142 entities form one community (single document). With multiple documents, Leiden would detect separate topic clusters.

### Community Report (Tier 3 — template)

```
Community: ebc796d2
Theme: This community centers around company (ORG) and 141 related entities.
Key entities: Ebenezer Scrooge (PERSON), Bob Cratchit (PERSON)...
Key relationships: Scrooge → Cratchit (weight 5.0)...
```

With an LLM configured (Ollama or OpenAI), the report would be a rich 300-word summary of themes, characters, and relationships.

---

## Pipeline Timings

| Step | Duration | Notes |
|------|----------|-------|
| Intake (12 states) | <1 second | File read + chunking |
| Embedding (71 chunks) | <1 second | Random vectors (fallback) |
| Indexing (3 stores) | <1 second | In-memory fallbacks |
| Graph projection | ~5 seconds | Entity extraction + resolution + relationships + communities |
| **Total** | **~6 seconds** | Full pipeline on phone (Termux) |

---

## Running Without the Demo Script

You can also do it through the API:

```bash
# 1. Ingest
curl -X POST http://127.0.0.1:8100/intake \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/christmas_carol.txt"}'

# 2. Search
curl -X POST http://127.0.0.1:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is Scrooge?", "top_k": 5}'

# 3. Graph query
curl -X POST http://127.0.0.1:8100/graphrag/query/local \
  -H "Content-Type: application/json" \
  -d '{"query": "Scrooge relationships", "user_principal": "public"}'

# 4. Check stats
curl http://127.0.0.1:8100/graphrag/stats
```

Or through the UI: upload the file via **Browse files** in the RAG tab.

---

## Source

- **Text:** "A Christmas Carol" by Charles Dickens (1843)
- **Source:** [Project Gutenberg](https://www.gutenberg.org/ebooks/24022)
- **License:** Public domain
- **Size:** 3,976 lines, ~170KB
- **Same dataset used by:** Microsoft GraphRAG official tutorial
