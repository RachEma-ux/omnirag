# OmniRAG Debugging Runbook

## 1. Common Issues & Fixes

| # | Symptom | Likely Cause | Fix |
|---|---|---|---|
| 1 | No results from `/v1/search` | Empty vector index, no documents ingested | Check `curl -s localhost:8120/collections/omnirag_chunks \| jq '.result.points_count'`. If 0, re-ingest documents via `POST /intake`. |
| 2 | All queries route to BASIC | Router BERT classifier not loaded or YAML rules all failing | Check logs for `search.query_routed` event. Verify classifier model exists at configured path. Check `omnirag/router/` config YAML is valid. |
| 3 | Entity extraction returns empty | spaCy model not installed or Ollama LLM unavailable for NER | Run `python -c "import spacy; spacy.load('en_core_web_sm')"`. Check Ollama: `curl -s localhost:8150/api/tags`. Install model: `python -m spacy download en_core_web_sm`. |
| 4 | Graph has 1 giant community | All entities connected via shared relationships; Louvain resolution too low | Check Louvain `resolution` parameter (default 1.0). Increase to 1.5-2.0 to split large community. Verify entity resolution is not merging too aggressively. |
| 5 | Slow search queries (> 10s) | Qdrant offline (falling back to brute force), or embedding generation slow | Check Qdrant: `curl -s localhost:8120/healthz`. Check embedding latency in logs. Check if Ollama model is loaded: `curl -s localhost:8150/api/ps`. |
| 6 | Intake stuck in DEFERRED state | Backpressure admission controller rejecting jobs | Check `curl -s localhost:8100/backpressure/health`. Check circuit breakers: `curl -s localhost:8100/backpressure/circuit-breakers`. Wait for recovery or manually reset. |
| 7 | Comments/graph data lost on restart | PostgreSQL not connected; in-memory fallback was used and lost | Verify `DATABASE_URL` is set and valid. Check `pg_isready -h localhost -p 8160`. Restart with working PostgreSQL to enable persistence. |
| 8 | `POST /intake` returns 429 | Rate limiter or token bucket exhausted | Check `curl -s localhost:8100/backpressure/health`. Wait for tokens to refill, or increase `token_bucket.max_tokens` in config. |
| 9 | GraphRAG query returns timeout | Neo4j query too complex, traversing entire graph | Check Neo4j query plan. Add indexes on frequently traversed properties. For global queries, ensure community reports are pre-computed. |
| 10 | Elasticsearch search returns stale data | Index not refreshed, or bulk indexing in progress | Force refresh: `curl -X POST localhost:8130/omnirag_documents/_refresh`. Check pending bulk operations. |
| 11 | Embeddings have wrong dimensions | Model changed but collection not recreated | Check model dimension vs collection dimension: `curl -s localhost:8120/collections/omnirag_chunks \| jq '.result.config.params.vectors.size'`. If mismatch, delete and recreate collection. |
| 12 | Redis connection refused | Redis down or port mismatch | `redis-cli -p 8140 ping`. If down, restart Redis. App will use in-memory fallback but loses cache coherence. |

---

## 2. Diagnostic Commands

### Full System Status Check

```bash
#!/bin/bash
# Save as check_omnirag.sh and run for quick diagnosis

echo "=== OmniRAG Application ==="
curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" http://localhost:8100/health
curl -s http://localhost:8100/health | jq -r '.components | to_entries[] | "\(.key): \(.value)"'

echo -e "\n=== Backpressure ==="
curl -s http://localhost:8100/backpressure/health | jq -r '.status'
curl -s http://localhost:8100/backpressure/circuit-breakers | jq -r '.breakers | to_entries[] | "\(.key): \(.value.state)"'

echo -e "\n=== Dead Letter Queue ==="
curl -s http://localhost:8100/dead-letters | jq -r '"DLQ depth: \(.count)"'

echo -e "\n=== PostgreSQL ==="
pg_isready -h localhost -p 8160 && echo "UP" || echo "DOWN"

echo -e "\n=== Neo4j ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8111/db/neo4j/cluster/available 2>/dev/null || echo "DOWN"

echo -e "\n=== Qdrant ==="
curl -s http://localhost:8120/healthz 2>/dev/null && echo "" || echo "DOWN"
curl -s http://localhost:8120/collections/omnirag_chunks 2>/dev/null | jq -r '"Vectors: \(.result.points_count // "N/A")"'

echo -e "\n=== Elasticsearch ==="
curl -s http://localhost:8130/_cluster/health 2>/dev/null | jq -r '"Cluster: \(.status), Nodes: \(.number_of_nodes)"' || echo "DOWN"

echo -e "\n=== Redis ==="
redis-cli -p 8140 ping 2>/dev/null || echo "DOWN"
redis-cli -p 8140 dbsize 2>/dev/null

echo -e "\n=== Ollama ==="
curl -s http://localhost:8150/api/tags 2>/dev/null | jq -r '.models[].name' || echo "DOWN"
curl -s http://localhost:8150/api/ps 2>/dev/null | jq -r '"Loaded: \(.models[].name)"' || echo "No models loaded"
```

### Check Individual Subsystems

```bash
# Search subsystem — end-to-end test
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 3}' | jq '{
    result_count: (.results | length),
    strategy: .metadata.strategy,
    latency_ms: .metadata.latency_ms
  }'

# Intake subsystem — check pipeline state distribution
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "intake stats"}' 2>/dev/null
# Better: query PostgreSQL directly
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT state, count(*) FROM intake_jobs GROUP BY state ORDER BY count DESC;"

# GraphRAG subsystem — stats
curl -s http://localhost:8100/graphrag/stats | jq .

# GraphRAG — test each query mode
for mode in local global drift; do
  echo "=== Mode: $mode ==="
  curl -s -X POST "http://localhost:8100/graphrag/query/$mode" \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}' | jq '{mode: .mode, result_count: (.results | length), error: .error}'
done

# Query router — check what mode a query resolves to
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the relationship between X and Y", "top_k": 1, "dry_run": true}' | jq '.metadata.route'

# Metrics endpoint — verify Prometheus scraping works
curl -s http://localhost:8100/metrics | head -20

# OpenTelemetry — check if traces are being generated
curl -s http://localhost:8100/metrics | grep -c "otel"
```

### Docker Container Diagnostics

```bash
# Container status
docker compose ps

# Container resource usage
docker stats --no-stream

# Application container logs (last 100 lines)
docker logs omnirag-app --tail 100

# Check OOM kills
docker inspect omnirag-app | jq '.[0].State.OOMKilled'

# Network connectivity between containers
docker exec omnirag-app curl -s http://omnirag-qdrant:6333/healthz
docker exec omnirag-app pg_isready -h omnirag-postgres -p 5432
docker exec omnirag-app redis-cli -h omnirag-redis -p 6379 ping
```

---

## 3. Log-Based Debugging

### Key structlog Event Names

| Event | Module | What It Means |
|---|---|---|
| `app.startup` | `_core` | Application starting; check for init errors after this |
| `app.ready` | `_core` | All services connected; ready to serve |
| `intake.registered` | `intake` | New ingestion job accepted |
| `intake.state_transition` | `intake` | Job moved states; fields: `job_id`, `from_state`, `to_state` |
| `intake.chunking_complete` | `intake` | Document chunked; fields: `job_id`, `chunk_count` |
| `intake.embedding_complete` | `intake` | Embeddings generated; fields: `job_id`, `vector_count` |
| `intake.indexing_complete` | `intake` | Vectors indexed in Qdrant; fields: `job_id`, `point_count` |
| `intake.job_active` | `intake` | Job fully processed and active |
| `intake.job_failed` | `intake` | Job failed; fields: `job_id`, `error`, `state` |
| `search.received` | `search` | Search request received; fields: `query`, `top_k` |
| `search.query_routed` | `router` | Router decided strategy; fields: `route`, `confidence`, `rule_matched` |
| `search.vector_results` | `retrieval` | Vector search returned; fields: `count`, `latency_ms` |
| `search.bm25_results` | `retrieval` | BM25 search returned; fields: `count`, `latency_ms` |
| `search.rrf_fused` | `retrieval` | RRF fusion complete; fields: `input_count`, `output_count` |
| `search.reranked` | `retrieval` | Reranker finished; fields: `input_count`, `output_count`, `latency_ms` |
| `search.completed` | `search` | Full search done; fields: `result_count`, `duration_seconds` |
| `graph.extraction_start` | `graphrag` | Entity extraction beginning for a document |
| `graph.entities_extracted` | `graphrag` | Entities found; fields: `entity_count`, `relation_count` |
| `graph.resolution_complete` | `graphrag` | Entity resolution done; fields: `merged_count` |
| `graph.communities_detected` | `graphrag` | Community detection done; fields: `community_count` |
| `graph.reports_generated` | `graphrag` | Community reports generated |
| `graph.query_complete` | `graphrag` | Graph query finished; fields: `mode`, `latency_ms` |
| `backpressure.token_exhausted` | `backpressure` | Token bucket empty |
| `backpressure.admission_rejected` | `backpressure` | Admission controller rejected request |
| `circuit_breaker.opened` | `backpressure` | Circuit breaker tripped; fields: `breaker`, `failure_count` |
| `circuit_breaker.closed` | `backpressure` | Circuit breaker recovered |
| `dead_letter.enqueued` | `backpressure` | Item sent to DLQ; fields: `job_id`, `reason` |
| `fallback.activated` | `persistence` | In-memory fallback active (backing service down) |
| `fallback.deactivated` | `persistence` | Backing service reconnected |

### Tracing a Request End-to-End

```bash
# 1. Find the request_id from access logs
docker logs omnirag-app --since 5m 2>&1 | jq 'select(.event == "search.received") | {request_id, query, timestamp}' | tail -5

# 2. Trace all events for that request
REQUEST_ID="paste-uuid-here"
docker logs omnirag-app --since 1h 2>&1 | jq "select(.request_id == \"$REQUEST_ID\")" | jq -r '"\(.timestamp) [\(.level)] \(.event) \(del(.timestamp, .level, .event, .request_id, .logger, .trace_id) | to_entries | map("\(.key)=\(.value)") | join(" "))"'

# 3. Get OpenTelemetry trace (if Jaeger/Zipkin is running)
TRACE_ID=$(docker logs omnirag-app --since 1h 2>&1 | jq -r "select(.request_id == \"$REQUEST_ID\") | .trace_id" | head -1)
echo "View trace at: http://localhost:16686/trace/$TRACE_ID"
```

---

## 4. Performance Profiling

### Identify Bottlenecks

Search latency breaks down into these phases:

```
Total Search Time = Routing + Embedding + Vector Search + BM25 Search + RRF Fusion + Reranking + Generation
```

```bash
# Get timing breakdown from logs for recent searches
docker logs omnirag-app --since 30m 2>&1 | jq '
  select(.event == "search.completed")
  | {
    total: .duration_seconds,
    route: .route_latency_ms,
    embedding: .embedding_latency_ms,
    vector: .vector_latency_ms,
    bm25: .bm25_latency_ms,
    fusion: .fusion_latency_ms,
    rerank: .rerank_latency_ms,
    generation: .generation_latency_ms
  }' | tail -10

# Prometheus: average time per phase over last 15 minutes
curl -s 'http://localhost:9090/api/v1/query?query=rate(omnirag_search_latency_seconds_sum[15m])/rate(omnirag_search_latency_seconds_count[15m])' | jq '.data.result[].value[1]'
```

### Common Bottleneck: Embedding Generation

```bash
# Check embedding latency
docker logs omnirag-app --since 30m 2>&1 | jq 'select(.event == "embedding.generation_complete") | .latency_ms' | sort -n | tail -5

# Check if Ollama model is loaded in GPU memory
curl -s http://localhost:8150/api/ps | jq '.models[] | {name, size, details}'

# Check Ollama resource usage
docker stats omnirag-ollama --no-stream
```

### Common Bottleneck: Vector Search

```bash
# Check Qdrant search latency directly
time curl -s -X POST http://localhost:8120/collections/omnirag_chunks/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3],
    "limit": 10,
    "with_payload": true
  }' > /dev/null

# Check if Qdrant is optimizing (rebuilding HNSW index)
curl -s http://localhost:8120/collections/omnirag_chunks | jq '.result.optimizer_status'
# "ok" = idle, "indexing" = busy (searches will be slower)

# Check collection shard count and segment info
curl -s http://localhost:8120/collections/omnirag_chunks/cluster | jq .
```

### Common Bottleneck: LLM Generation

```bash
# Check Ollama inference speed
curl -s -X POST http://localhost:8150/api/generate \
  -d '{"model": "llama3.2", "prompt": "Summarize: test", "stream": false}' | jq '{
    total_duration_ms: (.total_duration / 1000000),
    eval_count: .eval_count,
    tokens_per_second: (.eval_count / (.eval_duration / 1000000000))
  }'

# If tokens/second is low:
# 1. Check GPU memory: nvidia-smi (or rocm-smi)
# 2. Check if model fits in VRAM
# 3. Consider smaller quantization (Q4_K_M vs Q8)
```

---

## 5. State Machine Debugging

The intake pipeline has 12 states. A job should progress:

```
REGISTERED → VALIDATED → CHUNKING → CHUNKED → EMBEDDING → EMBEDDED → INDEXING → INDEXED → GRAPH_EXTRACTING → GRAPH_EXTRACTED → ACTIVATING → ACTIVE
```

Failure states: any state can transition to `FAILED` or `DEFERRED`.

### Trace a Job Through States

```bash
JOB_ID="paste-job-id-here"

# Get current state from PostgreSQL
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT id, state, error, created_at, updated_at FROM intake_jobs WHERE id = '$JOB_ID';"

# Get full state history from logs
docker logs omnirag-app --since 24h 2>&1 | jq "select(.job_id == \"$JOB_ID\" and .event == \"intake.state_transition\")" | jq -r '"\(.timestamp) \(.from_state) → \(.to_state)"'

# Find stuck jobs (in non-terminal state, not updated in 10 minutes)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT id, state, updated_at, now() - updated_at AS age
   FROM intake_jobs
   WHERE state NOT IN ('ACTIVE', 'FAILED')
     AND updated_at < now() - interval '10 minutes'
   ORDER BY updated_at ASC;"

# Re-queue a stuck job (if supported)
curl -s -X POST "http://localhost:8100/intake/$JOB_ID/retry" | jq .

# Check jobs stuck in DEFERRED (backpressure)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT id, state, error, updated_at FROM intake_jobs WHERE state = 'DEFERRED' ORDER BY updated_at ASC LIMIT 20;"

# Bulk retry all DEFERRED jobs (once backpressure clears)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "UPDATE intake_jobs SET state = 'REGISTERED', error = NULL, updated_at = now() WHERE state = 'DEFERRED';"

# Count jobs by state
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT state, count(*), min(updated_at) AS oldest, max(updated_at) AS newest FROM intake_jobs GROUP BY state ORDER BY count DESC;"
```

### Diagnosing State-Specific Failures

| Stuck State | What Failed | Check |
|---|---|---|
| VALIDATED | Chunking never started | Check worker process is running. Check logs for `intake.chunking_start`. |
| CHUNKING | Chunking crashed | Check logs for `intake.chunking_failed`. File may be corrupt or unsupported format. |
| EMBEDDING | Embedding generation failed | Check Ollama: `curl -s localhost:8150/api/ps`. Check for OOM in Ollama logs. |
| INDEXING | Vector DB insert failed | Check Qdrant: `curl -s localhost:8120/healthz`. Check dimension mismatch. |
| GRAPH_EXTRACTING | Entity extraction failed | Check spaCy model, Ollama availability, Neo4j connection. |
| DEFERRED | Backpressure rejected | Check `curl -s localhost:8100/backpressure/health`. Wait or increase limits. |

---

## 6. Graph Debugging

### Verify Entity Extraction

```bash
# Check entity count in Neo4j
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) RETURN count(e) AS entity_count"}]}' | jq '.results[0].data[0].row[0]'

# Check relationship count
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS rel_count"}]}' | jq '.results[0].data[0].row[0]'

# Sample entities (check quality)
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) RETURN e.name, e.type, e.description LIMIT 20"}]}' | jq '.results[0].data[] | .row'

# Check for entities with no relationships (orphans)
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) WHERE NOT (e)--() RETURN count(e) AS orphan_count"}]}' | jq '.results[0].data[0].row[0]'
```

### Verify Entity Resolution

```bash
# Check for near-duplicate entity names (resolution should have merged these)
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) WITH e.name AS name, count(*) AS cnt WHERE cnt > 1 RETURN name, cnt ORDER BY cnt DESC LIMIT 20"}]}' | jq '.results[0].data[] | .row'

# Check entity resolution log
docker logs omnirag-app --since 24h 2>&1 | jq 'select(.event == "graph.resolution_complete") | {merged_count, total_before, total_after}'
```

### Verify Community Detection

```bash
# Community count
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) RETURN count(DISTINCT e.community_id) AS community_count"}]}' | jq '.results[0].data[0].row[0]'

# Community size distribution
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) WITH e.community_id AS cid, count(*) AS size RETURN size, count(*) AS communities ORDER BY size DESC"}]}' | jq '.results[0].data[] | .row'

# Largest community (potential over-merging issue)
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) WITH e.community_id AS cid, count(*) AS size ORDER BY size DESC LIMIT 1 RETURN cid, size"}]}' | jq '.results[0].data[0].row'

# If largest community is > 50% of all entities, increase Louvain resolution:
# Edit config: graphrag.community_detection.resolution = 1.5 (default 1.0)
# Then rebuild: POST /graphrag/rebuild

# Check community reports exist
curl -s http://localhost:8100/graphrag/stats | jq '{entity_count, community_count, report_count}'
```

### GraphRAG Query Mode Diagnostics

```bash
# Test each query mode with timing
for mode in local global drift hybrid naive; do
  echo "=== $mode ==="
  START=$(date +%s%N)
  RESULT=$(curl -s -X POST "http://localhost:8100/graphrag/query/$mode" \
    -H "Content-Type: application/json" \
    -d '{"query": "What are the main topics?"}')
  END=$(date +%s%N)
  ELAPSED=$(( (END - START) / 1000000 ))
  echo "$RESULT" | jq -r "{mode: \"$mode\", latency_ms: $ELAPSED, result_count: (.results | length), error: .error}"
done

# If global mode fails: community reports not generated
# Fix: POST /graphrag/rebuild (triggers community detection + report generation)

# If drift mode fails: drift search requires graph + vector overlay
# Fix: Verify both Neo4j and Qdrant are healthy
```

### Rebuild Graph from Scratch

```bash
# Nuclear option: clear Neo4j and rebuild from PostgreSQL persisted state
# WARNING: This is destructive and takes time proportional to corpus size

# 1. Clear Neo4j
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (n) DETACH DELETE n"}]}'

# 2. Trigger graph rebuild from persisted documents
curl -s -X POST http://localhost:8100/graphrag/rebuild | jq .

# 3. Monitor progress
watch -n 5 'curl -s http://localhost:8100/graphrag/stats | jq .'
```
