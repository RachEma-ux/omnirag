# OmniRAG — Weakness Fix Plan

**Date:** 2026-04-05
**Scope:** All 7 identified weaknesses from post-build evaluation
**Agent:** Planner (report only)

---

## Weakness 1: Persistence is still thin

### Problem
Repository class has asyncpg code path but in-memory fallback is what runs. Jobs, documents, chunks, cursors — all gone on restart.

### Fix Plan

**Phase W1 — PostgreSQL persistence hardening**
**Files: ~3 | Lines: ~400**

1. `intake/storage/repository.py` — Upgrade to production-grade:
   - Connection pool health checks (auto-reconnect on failure)
   - Transaction batching (write jobs + source objects + documents + chunks in single transaction)
   - Retry on transient errors (connection reset, deadlock) with 3-attempt backoff
   - Migration versioning table (`schema_migrations`) — track which migrations have run
   - `UPSERT` using proper `ON CONFLICT` with composite keys (connector_id + external_id + version_ref)

2. `intake/storage/migrations.py` — Migration runner:
   - Reads SQL files in order (001_intake.sql, 002_output.sql, etc.)
   - Stores applied migrations in `schema_migrations` table
   - Forward-only (no rollback — append new migrations)

3. `tests/integration/test_persistence.py` — PostgreSQL integration tests:
   - Create test database (or use existing `omnirag_test`)
   - Test: upsert → get → list → delete cycle for every table
   - Test: concurrent writes don't deadlock
   - Test: restart recovery (write → kill → restart → data still there)
   - Test: large batch (1000 chunks) writes within timeout
   - Requires: `DATABASE_URL` env var pointing to real PostgreSQL

### Dependencies
```
asyncpg>=0.29  (already in optional deps)
```

### Acceptance criteria
- [ ] Server restarts with data intact
- [ ] 1000-chunk batch writes in <5 seconds
- [ ] Connection pool auto-recovers after PostgreSQL restart

---

## Weakness 2: No real Neo4j testing

### Problem
Graph store has complete Cypher code path but all development used networkx fallback. Zero confidence that Neo4j path works.

### Fix Plan

**Phase W2 — Neo4j integration testing**
**Files: ~3 | Lines: ~350**

4. `tests/integration/test_neo4j.py` — Full Neo4j test suite:
   - Connect to running Neo4j (skip if unavailable)
   - Test: create entity → retrieve → verify properties
   - Test: create relationship → verify weight accumulation
   - Test: ACL-filtered traversal (user sees only their entities)
   - Test: community creation → entity linking → report attachment
   - Test: `get_neighbors()` with max_hops=1 and max_hops=3
   - Test: `find_entity_by_name()` with aliases
   - Test: `get_chunks_for_entity()` with ACL filter
   - Test: full projection pipeline (chunks → entities → relationships → communities)
   - Test: cleanup (DETACH DELETE all test data)

5. `graphrag/store.py` — Fixes discovered during testing:
   - Fix Cypher syntax for Neo4j 5.x (constraint syntax differs from 4.x)
   - Add connection timeout + retry on bolt connection failure
   - Handle `ServiceUnavailable` exception → fallback to networkx gracefully
   - Add `verify_connection()` method called on startup

6. `docker/docker-compose.neo4j.yml` — Neo4j test instance:
   - Neo4j 5.x with APOC plugin
   - Bolt port 7687, HTTP port 7474
   - Default auth: neo4j/testpassword
   - Volume for persistence

### Dependencies
```
neo4j>=5.0  (already in optional deps)
```

### Acceptance criteria
- [ ] All 10 Neo4j tests pass against running instance
- [ ] Automatic fallback works when Neo4j is down
- [ ] Projection pipeline writes correct graph structure

---

## Weakness 3: No real Elasticsearch or Qdrant testing

### Problem
Hybrid retriever, RRF fusion, and cross-encoder reranking have never been tested against real Qdrant or Elasticsearch.

### Fix Plan

**Phase W3 — Qdrant + Elasticsearch integration testing**
**Files: ~4 | Lines: ~500**

7. `tests/integration/test_qdrant.py` — Qdrant test suite:
   - Connect to running Qdrant (skip if unavailable)
   - Test: create collection → upsert 100 vectors → search → verify results
   - Test: ACL payload filtering (user:alice sees her chunks only)
   - Test: cosine similarity ordering is correct
   - Test: delete chunks → verify removed from results
   - Test: large batch upsert (5000 vectors) performance

8. `tests/integration/test_elasticsearch.py` — Elasticsearch test suite:
   - Connect to running ES (skip if unavailable)
   - Test: create index → bulk write 100 docs → BM25 search → verify results
   - Test: ACL terms filter
   - Test: english analyzer (stemming, stopwords)
   - Test: delete docs → verify removed
   - Test: refresh timing (near-real-time)

9. `tests/integration/test_hybrid_retrieval.py` — End-to-end hybrid test:
   - Ingest 50 text files through full pipeline
   - Write to all 3 stores (vector + keyword + metadata)
   - Run hybrid search → verify RRF fusion produces better results than either alone
   - Test: vector-down fallback → keyword-only still returns results
   - Test: ES-down fallback → vector-only still returns results
   - Test: cross-encoder reranking improves order vs RRF alone

10. `docker/docker-compose.stores.yml` — Qdrant + ES test instances:
    - Qdrant 1.7+ on port 6333
    - Elasticsearch 8.x on port 9200 (single-node, no security)

### Dependencies
```
qdrant-client>=1.7      (already in optional deps)
elasticsearch[async]>=8.5  (already in optional deps)
```

### Acceptance criteria
- [ ] Qdrant: 100-vector search returns correct top-K
- [ ] Elasticsearch: BM25 search returns relevant results
- [ ] Hybrid: RRF fusion combines both lists correctly
- [ ] Fallback: each store failing independently doesn't crash the system

---

## Weakness 4: Entity extraction is basic

### Problem
Regex fallback extracts proper nouns but misses domain-specific entities. HDBSCAN resolution untested with real overlapping mentions.

### Fix Plan

**Phase W4 — Entity extraction upgrade**
**Files: ~4 | Lines: ~450**

11. `graphrag/extraction/entities.py` — Upgrade extractor:
    - Add Transformer-based NER option (dslim/bert-base-NER or similar)
    - Custom label mapping: map HuggingFace NER labels to our schema (PERSON, ORG, PRODUCT, PROJECT, REGULATORY_TERM)
    - Context window: feed previous + next chunk (500 chars) for coreference resolution
    - Confidence calibration: map model logits to 0-1 scale
    - Config: `ENTITY_EXTRACTOR_MODEL` env var to select model (spacy/transformer/regex)

12. `graphrag/extraction/resolution.py` — Harden entity resolution:
    - Test with real overlapping mentions: "MSFT", "Microsoft", "Microsoft Corp"
    - Add merge threshold tuning: `HDBSCAN_EPSILON` env var (default 0.15)
    - Add external KB linkage stub: query Wikidata SPARQL for canonical entity matches
    - Redis alias map: persist to Redis (not just in-memory) for cross-session resolution

13. `tests/integration/test_entity_extraction.py` — Entity tests:
    - Test: "Apple released the iPhone" → Entity(APPLE, ORG) + Entity(IPHONE, PRODUCT)
    - Test: "Microsoft", "MSFT", "Microsoft Corp" → all resolve to same entity
    - Test: context window helps resolve "it" → previously mentioned entity
    - Test: 1000-chunk extraction performance (<30 seconds)
    - Test: ACL propagation from chunks to entities (union logic)

14. Model download script: `scripts/download_models.sh`
    - Downloads spacy en_core_web_sm or en_core_web_trf
    - Downloads BERT NER model to local cache
    - Downloads sentence-transformers model for resolution

### Dependencies
```
transformers>=4.30   (new — for BERT NER)
spacy>=3.7           (already in optional deps)
```

### Acceptance criteria
- [ ] Transformer NER extracts domain entities with >0.8 precision
- [ ] "Microsoft" + "MSFT" resolve to same entity
- [ ] Context window improves coreference resolution
- [ ] 1000 chunks processed in <30 seconds

---

## Weakness 5: BERT query router is a stub

### Problem
Stage 2 of the router falls back to heuristic keyword matching. No trained model, no labelled dataset.

### Fix Plan

**Phase W5 — Query router model training**
**Files: ~5 | Lines: ~500**

15. `graphrag/router/training_data.py` — Generate training dataset:
    - Use LLM (GPT-4 or local) to generate 10,000 labelled queries:
      - 2,500 BASIC ("What is X?", "Define Y", "When did Z happen?")
      - 2,500 LOCAL ("How is X related to Y?", "Details about X", "What does X say about Y?")
      - 2,500 GLOBAL ("Summarize all themes", "Overview of the corpus", "What are the main risks?")
      - 2,500 DRIFT ("Investigate how X connects to Y", "Explore the relationship", "Connect the dots")
    - Human validation: sample 500 queries, verify labels
    - Save as JSONL: `data/router_training.jsonl`

16. `graphrag/router/train.py` — Training script:
    - Model: distilbert-base-uncased
    - Classification head: 4 classes
    - Hyperparameters: batch=32, lr=2e-5, epochs=3, AdamW
    - Validation split: 80/20
    - Export: ONNX format for fast inference
    - Save to: `models/router_classifier/`

17. `graphrag/router/classifier.py` — Production classifier:
    - Load ONNX model on startup (fallback to heuristics if model not found)
    - Tokenize → inference → softmax → confidence threshold (0.7)
    - Batch support: classify multiple queries at once
    - Latency target: <10ms per query

18. `graphrag/router/router.py` — Update stage 2:
    - Replace HTTP stub with local ONNX inference
    - Add `ROUTER_MODEL_PATH` env var
    - Log classifier usage rate vs rule-based rate (for metrics)

19. `tests/integration/test_router.py` — Router tests:
    - Test: "What is RAG?" → BASIC (rule-based)
    - Test: "How is OmniRAG related to Neo4j?" → LOCAL (rule-based)
    - Test: "Summarize all themes" → GLOBAL (rule-based)
    - Test: ambiguous query → BERT classifier invoked
    - Test: low-confidence BERT → fallback to BASIC
    - Test: dynamic override BASIC→LOCAL when confidence <0.62

### Dependencies
```
transformers>=4.30   (shared with W4)
onnxruntime>=1.16    (new — fast inference)
datasets>=2.14       (new — training data handling)
```

### Acceptance criteria
- [ ] 10,000 labelled queries generated
- [ ] Trained model achieves >85% accuracy on validation set
- [ ] ONNX inference <10ms per query
- [ ] Router uses model when available, heuristics when not

---

## Weakness 6: No async embedding pipeline

### Problem
Embedding is synchronous in-process. Blocks the intake pipeline. Won't scale to multi-worker.

### Fix Plan

**Phase W6 — Async embedding pipeline**
**Files: ~4 | Lines: ~400**

20. `output/embedding_worker.py` — Background embedding worker:
    - Asyncio task queue (in-process, upgradeable to Kafka)
    - Consumes from: `embedding_queue` (asyncio.Queue)
    - Produces to: vector index writer
    - Batch: accumulate 256 chunks, then embed + write
    - Retry: 3 attempts with backoff on failure
    - DLQ: failed chunks go to dead-letter
    - Status tracking: embedding_status per chunk (pending/completed/failed)
    - Commit event: after batch write, increment index_version

21. `output/embedding_queue.py` — Queue abstraction:
    - Interface: `put(chunks)`, `get_batch(max_size, timeout)`
    - In-process: `asyncio.Queue` (default)
    - Kafka: `aiokafka.AIOKafkaProducer` / `Consumer` (when `KAFKA_BROKERS` env set)
    - Topic: `chunk.embedding.requests`
    - DLQ topic: `chunk.embedding.dlq`

22. Wire into intake gate:
    - After CHUNKED state: push chunks to embedding queue (non-blocking)
    - INDEXED state waits for embedding completion (or proceeds with metadata-only)
    - Separate "embedding complete" callback triggers consistency commit

23. `tests/integration/test_async_embedding.py`:
    - Test: 500 chunks queued → all embedded within 30 seconds
    - Test: worker failure → retry → eventual completion
    - Test: DLQ captures permanent failures
    - Test: embedding_status tracked correctly

### Dependencies
```
aiokafka>=0.10  (new — optional, for Kafka mode)
```

### Acceptance criteria
- [ ] Embedding runs in background, doesn't block intake
- [ ] 500 chunks embedded in <30 seconds
- [ ] DLQ captures failures
- [ ] Kafka mode works when broker available

---

## Weakness 7: Community reports depend on LLM availability

### Problem
No LLM configured → community reports are just entity name lists → Global and DRIFT search quality drops to near zero.

### Fix Plan

**Phase W7 — Resilient community reports**
**Files: ~3 | Lines: ~300**

24. `graphrag/extraction/reports.py` — Multi-tier report generation:
    - **Tier 1: LLM available** — full 300-word summary via configured adapter (existing)
    - **Tier 2: Local small model** — use a small local model (TinyLlama, Phi-3-mini, or similar via Ollama) as fallback when primary LLM unavailable
    - **Tier 3: Template-based** — no LLM at all: generate structured report from entity + relationship data using templates:
      ```
      Community: {community_id}
      Theme: {most_connected_entity} and related concepts
      Key entities ({count}): {entity_1} ({type}), {entity_2} ({type}), ...
      Key relationships: {entity_a} → {entity_b} (weight {w}), ...
      Summary: This community centers around {top_entity} with {n} connected entities.
      The strongest relationship is between {e1} and {e2}.
      ```
    - Auto-detect tier: try Tier 1 → timeout 10s → try Tier 2 → timeout 5s → Tier 3
    - Tag report with `generation_tier: 1|2|3` for quality tracking

25. `graphrag/extraction/report_templates.py` — Template engine:
    - Slot-filling from entity + relationship data
    - Handles: single-entity communities, large communities (>20 entities), hierarchical communities
    - Quality score: tier 1 = 1.0, tier 2 = 0.7, tier 3 = 0.4

26. `tests/integration/test_community_reports.py`:
    - Test: Tier 1 generates rich summary when LLM available
    - Test: Tier 2 falls back to local model when primary times out
    - Test: Tier 3 generates template-based report when no LLM at all
    - Test: quality score attached to report
    - Test: Global search still returns useful results with Tier 3 reports

### Dependencies
None new — uses existing LLM adapter infrastructure.

### Acceptance criteria
- [ ] Reports generated at every tier (1, 2, 3)
- [ ] No LLM = Tier 3 template still produces searchable reports
- [ ] Global search works (degraded quality but not broken) with Tier 3
- [ ] Report quality score visible in metrics

---

## Execution Order

```
W1 (persistence)        ← foundation, everything needs it
  ↓
W6 (async embedding)    ← needed for W3 at scale
  ↓
W3 (Qdrant + ES tests)  ← validates output layer
W2 (Neo4j tests)         ← validates graph layer
  ↓ (parallel)
W4 (entity extraction)  ← improves graph quality
W7 (resilient reports)  ← improves search quality
  ↓
W5 (BERT router)        ← requires W4 + W7 for training data
```

### Can be parallelized:
- W2 + W3 (independent backing store tests)
- W4 + W7 (independent quality improvements)

---

## Docker Compose (for all testing)

```yaml
# docker/docker-compose.full.yml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: omnirag
      POSTGRES_PASSWORD: omnirag

  neo4j:
    image: neo4j:5-community
    ports: ["7687:7687", "7474:7474"]
    environment:
      NEO4J_AUTH: neo4j/testpassword

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]

  elasticsearch:
    image: elasticsearch:8.12.0
    ports: ["9200:9200"]
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

One command: `docker-compose -f docker/docker-compose.full.yml up -d`

---

## Estimated Total Scope

| Phase | Focus | Files | Lines |
|-------|-------|-------|-------|
| W1 | PostgreSQL persistence hardening | 3 | ~400 |
| W2 | Neo4j integration testing | 3 | ~350 |
| W3 | Qdrant + ES integration testing | 4 | ~500 |
| W4 | Entity extraction upgrade | 4 | ~450 |
| W5 | BERT query router training | 5 | ~500 |
| W6 | Async embedding pipeline | 4 | ~400 |
| W7 | Resilient community reports | 3 | ~300 |
| **Total** | | **~26** | **~2,900** |

### After weakness fixes:

```
Existing platform:     87 files,  7,679 lines  ✅
Weakness fixes (W1–7): 26 files, ~2,900 lines  ← planned
Docker Compose:         1 file,     ~30 lines  ← planned
─────────────────────────────────────────────────────────
Total:               ~114 files, ~10,600 lines
```

---

## Maturity After Fixes

```
[Toy] ─── [Prototype] ─── [MVP] ─── [Production] ─── [Enterprise]
                                            ▲
                                       After W1–W7
```

The system moves from "strong MVP" to "production-ready" — all backing stores validated, models trained, embedding async, reports resilient, persistence battle-tested.

Awaiting approval to proceed.
