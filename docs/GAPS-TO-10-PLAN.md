# OmniRAG — Plan to Close All Gaps (8.2 → 10.0)

**Date:** 2026-04-05
**Baseline:** v4.0.0-ground-zero (a910e0b)
**Current score:** 8.2 / 10
**Target score:** 10.0 / 10

---

## Gap Map

| # | Gap | Points Lost | Current | Target |
|---|-----|-------------|---------|--------|
| 1 | In-memory only | -0.6 | Data lost on restart | Data survives restart |
| 2 | No real backing store testing | -0.4 | All fallbacks | Tests pass against real stores |
| 3 | Models untrained | -0.3 | Heuristic fallbacks | Trained BERT + NER |
| 4 | Frontends are scaffolds | -0.3 | Next.js/Chainlit stubs | Full working apps |
| 5 | No CI/CD, no Dockerfile | -0.2 | Manual push, manual run | Automated pipeline |

**Total gap: 1.8 points**

---

## Phase OP1 — PostgreSQL Persistence (fixes -0.6)

**Goal:** Every piece of data survives server restart.

### What to wire:

| Data | Current Storage | Target Storage | Table |
|------|----------------|---------------|-------|
| Intake jobs | In-memory dict | PostgreSQL | `sync_jobs` |
| Source objects | In-memory dict | PostgreSQL | `source_objects` |
| Canonical documents | In-memory dict | PostgreSQL | `canonical_documents` |
| Chunks | In-memory dict | PostgreSQL | `chunks` |
| Chunk embeddings | In-memory dict | pgvector `chunks.embedding` column |
| Graph entities | In-memory dict | PostgreSQL `entities` + Neo4j |
| Graph relationships | In-memory list | PostgreSQL `relationships` + Neo4j |
| Communities | In-memory dict | PostgreSQL `communities` |
| Community reports | In-memory dict | PostgreSQL `community_reports` |
| ACL snapshots | In-memory dict | PostgreSQL `acl_snapshots` |
| Lineage events | In-memory list | PostgreSQL `lineage_events` |
| Dead letters | In-memory dict | PostgreSQL `dead_letters` |
| Cursors | In-memory dict | PostgreSQL `source_cursors` |
| Query traces | In-memory dict | PostgreSQL `query_traces` |
| Metric events | In-memory list | PostgreSQL `metric_events` |
| Comments | In-memory dict | PostgreSQL `graph_comments` |
| Cache | In-memory dict | Redis |

### Implementation steps:

1. **Ensure PostgreSQL running on port 8160** (or system 5432)
   ```bash
   createdb omnirag
   ```

2. **Run all migrations on startup** — already implemented in `migrations.py`

3. **Wire Repository into every store module:**
   - `intake/gate.py` — already calls `repo.save_*()` after ACTIVE (done)
   - `graphrag/store.py` — add `repo.save_*()` after every entity/relationship/community upsert
   - `output/index_writers/keyword.py` — persist chunks to PostgreSQL
   - `output/index_writers/metadata.py` — persist to PostgreSQL
   - `graphrag/cache.py` — wire Redis (or PostgreSQL fallback)
   - `output/tracing.py` — already calls `repo.upsert()` (done)
   - `api/routes/graph_comments.py` — wire to PostgreSQL

4. **On startup: load from PostgreSQL into memory**
   - Load all entities, relationships, communities into graph store
   - Load all chunks into keyword/metadata writers
   - Load cursors into cursor store
   - This means: restart → full state restored in seconds

5. **Test: restart survival**
   - Ingest document → kill server → restart → query → same results

### Files changed: ~8
### Lines: ~400
### Points recovered: +0.6

---

## Phase OP2 — Real Backing Store Testing (fixes -0.4)

**Goal:** All 92 tests pass against Docker Compose services.

### Steps:

1. **Start Docker Compose**
   ```bash
   docker-compose -f docker/docker-compose.full.yml up -d
   ```
   Services: PostgreSQL:8160, Neo4j:8110, Qdrant:8120, ES:8130, Redis:8140

2. **Configure env for tests**
   ```bash
   export DATABASE_URL=postgresql://omnirag:omnirag@localhost:8160/omnirag
   export NEO4J_URI=bolt://localhost:8110
   export QDRANT_HOST=localhost
   export QDRANT_PORT=8120
   export ELASTICSEARCH_URL=http://localhost:8130
   export REDIS_ADDR=localhost:8140
   ```

3. **Fix connection issues discovered during testing:**
   - Neo4j Cypher syntax differences (5.x vs 4.x)
   - Qdrant collection auto-creation timing
   - ES index refresh timing (near-real-time)
   - Redis connection pool sizing
   - PostgreSQL schema migration ordering

4. **Add test markers:**
   ```python
   @pytest.mark.integration  # requires Docker
   @pytest.mark.unit          # runs anywhere
   ```

5. **Run and fix until green:**
   ```bash
   pytest tests/ -v --timeout=30
   ```

6. **Performance baselines:**
   - Ingest 100 pages: < 60 seconds
   - Query p95: < 2 seconds
   - Keyword search: < 500ms
   - Vector search: < 500ms
   - Graph traversal: < 1 second

### Files changed: ~5 (test files + connection fixes)
### Lines: ~300
### Points recovered: +0.4

---

## Phase OP3 — Model Training (fixes -0.3)

**Goal:** Trained BERT router + improved NER. Real models, not heuristics.

### 3a. BERT Query Router

1. **Generate training data** (script exists: `router/training_data.py`)
   ```bash
   python -c "
   from omnirag.graphrag.router.training_data import generate_training_data
   generate_training_data('data/router_training.jsonl', count_per_class=2500)
   "
   ```
   Output: 10,000 labelled queries (2,500 × 4 classes)

2. **Train model** (script exists: `router/train.py`)
   ```bash
   python -m omnirag.graphrag.router.train \
     --data data/router_training.jsonl \
     --output models/router_classifier \
     --epochs 3 --batch-size 32 --lr 2e-5
   ```
   Requires: GPU machine or Colab (15-30 minutes on T4)

3. **Export ONNX** (included in train.py)
   Output: `models/router_classifier/model.onnx` (~66MB)

4. **Deploy:** Copy model directory to server, set env:
   ```bash
   export ROUTER_MODEL_PATH=models/router_classifier
   ```

5. **Validate:** Run router tests with model loaded
   Target: >85% accuracy on validation set, <10ms inference

### 3b. Entity Extraction (NER)

1. **Download spaCy model:**
   ```bash
   python -m spacy download en_core_web_sm
   ```
   Or for better quality:
   ```bash
   python -m spacy download en_core_web_trf
   ```

2. **Download sentence-transformers** (for entity resolution):
   ```bash
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
   ```

3. **Optional: fine-tune NER** for domain entities
   Using spaCy's training pipeline with custom labels

4. **Model download script:**
   ```bash
   # scripts/download_models.sh
   pip install spacy sentence-transformers
   python -m spacy download en_core_web_sm
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
   ```

### Files changed: ~3 (scripts + config)
### Lines: ~100
### Points recovered: +0.3

---

## Phase OP4 — Frontend Build-Out (fixes -0.3)

**Goal:** Next.js and Chainlit are full working apps, not scaffolds.

### 4a. Next.js Frontend

Current: `frontend/app/page.tsx` with placeholder tabs.
Target: Full React app matching current vanilla JS functionality.

**Pages to build:**

| Page | Current (vanilla JS) | Next.js equivalent |
|------|--------------------|--------------------|
| RAG tab | Intake + pipelines + adapters | `app/page.tsx` |
| OmniGraph tab | Query + services + router | `app/omnigraph/page.tsx` |
| Visualization tab | Canvas graph | `app/visualization/page.tsx` |
| Chat tab | Composer + messages | `app/chat/page.tsx` |
| Settings | Adapter config | `app/settings/page.tsx` |
| API Docs | Embedded iframe | `app/docs/page.tsx` |

**Components to build:**

```
components/
  shell/
    sidebar.tsx         — rail + panel + drawer (from OpenCode template)
    titlebar.tsx        — brand + links + export
    footer.tsx          — status bar
    tabs.tsx            — 4-tab switcher
  graph/
    canvas.tsx          — React wrapper for graph canvas
    filters.tsx         — filter panel component
    node-detail.tsx     — entity detail panel
    legend.tsx          — color legend
  chat/
    message-list.tsx    — user + assistant messages
    composer.tsx        — input + toolbar
  intake/
    source-input.tsx    — URI input + file picker
    job-list.tsx        — intake jobs table
  adapters/
    adapter-card.tsx    — interactive adapter config
```

**Shared:**
```
lib/
  api.ts              — typed API client (already exists)
  types.ts            — TypeScript types matching Python models
  hooks/
    use-graph.ts      — graph data fetching + state
    use-search.ts     — search query hook
```

### 4b. Chainlit Ops UI

Current: `ops-ui/app.py` with basic query handler.
Target: Full ops interface with trace inspection.

**Features to build:**

| Feature | Implementation |
|---------|---------------|
| Interactive query | Already done — send query, show answer |
| Trace inspection | After query: show QueryPlan → ContextBundle → LLM call → latency |
| Ingestion monitor | `/status` command: show running jobs, errors, counts |
| Graph browser | `/graph` command: entity lookup, community list |
| Pipeline replay | `/replay {job_id}`: show step-by-step state transitions |
| Model status | `/models`: show which models are loaded (BERT, NER, embedding) |

### Files: ~25 (Next.js) + ~5 (Chainlit)
### Lines: ~3,000
### Points recovered: +0.3

---

## Phase OP5 — CI/CD + Dockerfile (fixes -0.2)

**Goal:** Automated testing and one-command deployment.

### 5a. Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[all]" && \
    python -m spacy download en_core_web_sm
EXPOSE 8100
CMD ["omnirag", "serve", "--host", "0.0.0.0", "--port", "8100"]
```

### 5b. GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install ruff && ruff check omnirag/

  test-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -e ".[dev]" && pytest tests/ -m "not integration" -v

  test-integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_DB: omnirag, POSTGRES_PASSWORD: omnirag }
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v
        env:
          DATABASE_URL: postgresql://postgres:omnirag@localhost:5432/omnirag
          REDIS_ADDR: localhost:6379

  build-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t omnirag:test .
      - run: docker run --rm omnirag:test omnirag --version
```

### 5c. Deploy workflow (optional)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    tags: ["v*"]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t omnirag:${{ github.ref_name }} .
      - run: docker push registry/omnirag:${{ github.ref_name }}
```

### Files: ~4 (Dockerfile + 2 workflows + .dockerignore)
### Lines: ~150
### Points recovered: +0.2

---

## Execution Order

```
OP1 (persistence)  → OP2 (store testing) → OP5 (CI/CD + Docker)
                                                ↓
                   OP3 (model training)   → OP4 (frontends)
```

OP1 must come first — everything else depends on real persistence.
OP3 can run in parallel (needs GPU, independent of code).
OP4 is the largest effort but lowest dependency.
OP5 should come early to catch regressions.

---

## Estimated Scope

| Phase | Focus | Files | Lines | Points |
|-------|-------|-------|-------|--------|
| OP1 | PostgreSQL persistence | ~8 | ~400 | +0.6 |
| OP2 | Docker Compose testing | ~5 | ~300 | +0.4 |
| OP3 | Model training | ~3 | ~100 | +0.3 |
| OP4 | Next.js + Chainlit | ~30 | ~3,000 | +0.3 |
| OP5 | CI/CD + Dockerfile | ~4 | ~150 | +0.2 |
| **Total** | | **~50** | **~3,950** | **+1.8** |

---

## Score Progression

```
Current:  8.2 / 10  (v4.0.0-ground-zero)
After OP1: 8.8      (data survives restart)
After OP2: 9.2      (tests pass against real stores)
After OP3: 9.5      (trained models)
After OP4: 9.8      (full frontends)
After OP5: 10.0     (CI/CD, Docker, production-ready)
```

---

## After All Gaps Closed

```
Platform:         ~218 files, ~18,700 lines
Tests:            92 unit + ~20 integration (against real stores)
CI:               Lint → Unit test → Integration test → Docker build
Models:           BERT router (85%+) + spaCy NER + sentence-transformers
Persistence:      PostgreSQL (all data) + Redis (cache) + Neo4j (graph)
Frontend:         Next.js (full app) + Chainlit (ops)
Deployment:       docker build → docker run → production
Score:            10.0 / 10
```

**Enterprise-grade. Production-ready. Battle-tested. Nothing left to defer.**

Awaiting approval to proceed.
