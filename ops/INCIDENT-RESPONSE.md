# OmniRAG Incident Response Runbook

## 1. Severity Levels

| Level | Name | Definition | Response Time | Examples |
|---|---|---|---|---|
| **P1** | Critical | Service completely unavailable; no queries or ingestion possible | 5 minutes | OmniRAG process down, PostgreSQL down, all circuit breakers open |
| **P2** | Degraded | Service running but with significant quality or performance loss | 15 minutes | Search returning poor results, intake pipeline stalled, high latency (> 15s P95) |
| **P3** | Component Failure | Single backing service down but system functioning via fallback | 1 hour | Redis down (cache miss), Neo4j down (graph queries fail, vector search works), Ollama down (no generation) |
| **P4** | Warning | Anomalous metrics but no user impact yet | 4 hours | DLQ growing, cache hit rate declining, one circuit breaker open |

---

## 2. First Response Checklist

For **any** incident, execute these 5 steps in order before proceeding to a specific runbook:

### Step 1: Confirm the Problem (30 seconds)

```bash
# Application responding?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/health

# Get full health breakdown
curl -s http://localhost:8100/health | jq .
```

### Step 2: Check Process State (30 seconds)

```bash
# Is the process running?
docker compose ps

# Resource usage (CPU, memory, network)
docker stats --no-stream

# Recent OOM kills
docker inspect omnirag-app 2>/dev/null | jq '.[0].State.OOMKilled'
```

### Step 3: Check Recent Errors (1 minute)

```bash
# Last 50 error-level log lines
docker logs omnirag-app --since 10m 2>&1 | jq 'select(.level == "error")' | tail -50

# Any crash/restart events
docker logs omnirag-app --since 10m 2>&1 | jq 'select(.event == "app.startup" or .event == "app.shutdown")' 
```

### Step 4: Check Backing Services (1 minute)

```bash
pg_isready -h localhost -p 8160 && echo "PG: UP" || echo "PG: DOWN"
curl -sf http://localhost:8120/healthz > /dev/null && echo "Qdrant: UP" || echo "Qdrant: DOWN"
curl -sf http://localhost:8130/_cluster/health > /dev/null && echo "ES: UP" || echo "ES: DOWN"
redis-cli -p 8140 ping 2>/dev/null | grep -q PONG && echo "Redis: UP" || echo "Redis: DOWN"
curl -sf http://localhost:8111/db/neo4j/cluster/available > /dev/null && echo "Neo4j: UP" || echo "Neo4j: DOWN"
curl -sf http://localhost:8150/api/tags > /dev/null && echo "Ollama: UP" || echo "Ollama: DOWN"
```

### Step 5: Record Incident Start

Note and communicate:
- **Time detected**: UTC timestamp
- **Reported by**: Alert name or person
- **Initial assessment**: P1/P2/P3/P4
- **Affected functionality**: search / intake / graph / all
- **Current status of backing services**: which are up/down

---

## 3. Runbook: Service Unavailable (P1)

**Trigger**: `/health` returns non-200 or connection refused.

### 3.1 Process Not Running

```bash
# Check if container is running
docker compose ps omnirag-app

# Check exit code
docker inspect omnirag-app | jq '.[0].State'

# Check for OOM kill
docker inspect omnirag-app | jq '.[0].State.OOMKilled'
# If true: increase memory limit in docker-compose.yml and restart

# Check last logs before crash
docker logs omnirag-app --tail 100 2>&1 | jq 'select(.level == "error" or .level == "fatal")' | tail -20

# Restart
docker compose up -d omnirag-app

# Verify recovery
sleep 10
curl -s http://localhost:8100/health | jq .
```

### 3.2 Process Running But Not Responding

```bash
# Check if port is listening
ss -tlnp | grep 8100

# Check thread/connection count
docker exec omnirag-app sh -c 'ls /proc/1/fd | wc -l'

# Check if process is deadlocked (high CPU, no responses)
docker exec omnirag-app sh -c 'cat /proc/1/status | grep -E "Threads|VmRSS"'

# Force restart if unresponsive
docker compose restart omnirag-app

# Verify
sleep 10
curl -s http://localhost:8100/health | jq .
```

### 3.3 Startup Failure (Exits Immediately)

```bash
# Check startup logs
docker logs omnirag-app 2>&1 | head -50

# Common causes:
# 1. DATABASE_URL invalid → check env vars
docker compose config | grep DATABASE_URL

# 2. Port conflict
ss -tlnp | grep 8100

# 3. Migration failure
docker logs omnirag-app 2>&1 | grep -i "migration\|alembic"

# 4. Config file syntax error
docker exec omnirag-app python -c "import yaml; yaml.safe_load(open('config.yml'))"
```

### 3.4 PostgreSQL Down (Cascading P1)

PostgreSQL is the persistence backbone. If it is down, new intake fails and state is lost.

```bash
# Check PostgreSQL container
docker compose ps omnirag-postgres
docker logs omnirag-postgres --tail 50

# Check disk space (common cause)
docker exec omnirag-postgres df -h /var/lib/postgresql/data

# Check for corrupted WAL
docker logs omnirag-postgres 2>&1 | grep -i "corrupt\|wal\|panic"

# Restart PostgreSQL
docker compose restart omnirag-postgres

# Verify
sleep 5
pg_isready -h localhost -p 8160

# Then restart app to reconnect
docker compose restart omnirag-app
```

---

## 4. Runbook: Search Quality Degraded (P2)

**Trigger**: Users report irrelevant results; search quality metrics dropping.

### 4.1 Diagnose the Problem

```bash
# Test search and inspect routing decision
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "a known topic in your corpus", "top_k": 5}' | jq '{
    result_count: (.results | length),
    strategy: .metadata.strategy,
    scores: [.results[].score]
  }'
```

### 4.2 Problem: All Queries Routing to BASIC

```bash
# Check recent routing decisions
docker logs omnirag-app --since 30m 2>&1 | jq 'select(.event == "search.query_routed") | {route, confidence, rule_matched}' | tail -20

# If all routes are "BASIC":
# 1. Check if YAML rules file is readable
docker exec omnirag-app ls -la omnirag/router/rules.yml

# 2. Check if BERT classifier model exists
docker exec omnirag-app ls -la omnirag/router/model/

# 3. Check router initialization logs
docker logs omnirag-app 2>&1 | jq 'select(.event | startswith("router."))' | head -20

# Fix: Restart app to re-initialize router
docker compose restart omnirag-app
```

### 4.3 Problem: Vector Search Returns No Results

```bash
# Check Qdrant collection exists and has vectors
curl -s http://localhost:8120/collections/omnirag_chunks | jq '{
  points_count: .result.points_count,
  status: .result.status,
  optimizer_status: .result.optimizer_status
}'

# If points_count is 0: documents were never embedded/indexed
# Re-ingest documents

# If status is not "green": Qdrant may be rebuilding index
# Wait for optimizer to finish

# Test direct vector search (use a dummy vector of correct dimension)
DIM=$(curl -s http://localhost:8120/collections/omnirag_chunks | jq '.result.config.params.vectors.size')
VECTOR=$(python3 -c "import json; print(json.dumps([0.1]*$DIM))")
curl -s -X POST http://localhost:8120/collections/omnirag_chunks/points/search \
  -H "Content-Type: application/json" \
  -d "{\"vector\": $VECTOR, \"limit\": 3}" | jq '.result | length'
```

### 4.4 Problem: BM25/Elasticsearch Returns Stale Results

```bash
# Check document count in ES
curl -s http://localhost:8130/omnirag_documents/_count | jq .count

# Force index refresh
curl -s -X POST http://localhost:8130/omnirag_documents/_refresh

# Check if mapping is correct (analyzer, tokenizer)
curl -s http://localhost:8130/omnirag_documents/_mapping | jq '.omnirag_documents.mappings.properties | keys'

# Reindex if needed
curl -s -X POST http://localhost:8130/_reindex \
  -H "Content-Type: application/json" \
  -d '{"source": {"index": "omnirag_documents"}, "dest": {"index": "omnirag_documents_v2"}}'
```

### 4.5 Problem: Reranker Failing Silently

```bash
# Check reranker logs
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.event | startswith("rerank"))' | tail -10

# If reranker is unavailable, results are returned un-reranked (lower quality)
# Check if reranker model is loaded in Ollama
curl -s http://localhost:8150/api/tags | jq '.models[].name'
```

---

## 5. Runbook: Intake Pipeline Stalled (P2)

**Trigger**: `omnirag_intake_jobs_in_progress` is non-zero but no state transitions occurring.

### 5.1 Assess the Situation

```bash
# Current state distribution
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT state, count(*), min(updated_at) AS oldest_stale
   FROM intake_jobs
   WHERE state NOT IN ('ACTIVE', 'FAILED')
   GROUP BY state ORDER BY count DESC;"

# Check backpressure
curl -s http://localhost:8100/backpressure/health | jq .

# Check circuit breakers
curl -s http://localhost:8100/backpressure/circuit-breakers | jq '.breakers | to_entries[] | {name: .key, state: .value.state, failures: .value.failure_count}'

# Check dead letter queue
curl -s http://localhost:8100/dead-letters | jq '{count: .count, oldest: .items[0].timestamp, newest: .items[-1].timestamp}'
```

### 5.2 Backpressure Is Blocking Admission

```bash
# Check token bucket
curl -s http://localhost:8100/backpressure/health | jq '{
  token_bucket: .token_bucket,
  admission_rate: .admission_rate,
  queue_depth: .queue_depth
}'

# If tokens exhausted: either wait for refill or increase rate
# Temporary increase (if API supports it):
curl -s -X POST http://localhost:8100/backpressure/config \
  -H "Content-Type: application/json" \
  -d '{"token_bucket": {"max_tokens": 200, "refill_rate": 20}}'

# Move DEFERRED jobs back to REGISTERED
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "UPDATE intake_jobs SET state = 'REGISTERED', error = NULL, updated_at = now()
   WHERE state = 'DEFERRED'
   RETURNING id, state;"
```

### 5.3 Circuit Breaker Tripped

```bash
# Identify which breaker is open
curl -s http://localhost:8100/backpressure/circuit-breakers | jq '.breakers | to_entries[] | select(.value.state == "open")'

# The breaker name tells you which service is failing:
# - "qdrant" → Qdrant vector DB
# - "elasticsearch" → ES keyword search
# - "ollama" → LLM inference/embedding
# - "neo4j" → Graph store
# - "postgresql" → Main persistence

# Fix the underlying service (see Section 4 of MONITORING.md for health checks)
# Then wait for circuit breaker to transition: OPEN → HALF_OPEN → CLOSED

# Monitor circuit breaker recovery
watch -n 5 'curl -s http://localhost:8100/backpressure/circuit-breakers | jq ".breakers"'
```

### 5.4 Worker Process Stuck

```bash
# Check for stuck workers in logs
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.event | test("intake\\.(chunking|embedding|indexing)_start")) | {event, job_id, timestamp}' | tail -10

# Compare with completion events
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.event | test("intake\\.(chunking|embedding|indexing)_complete|intake.job_failed")) | {event, job_id, timestamp}' | tail -10

# If a job started but never completed/failed: worker may be hung
# Restart the app to reset workers
docker compose restart omnirag-app
```

### 5.5 Dead Letter Queue Processing

```bash
# View DLQ contents
curl -s http://localhost:8100/dead-letters | jq '.items[:5] | .[] | {job_id, error, timestamp, retry_count}'

# Retry specific DLQ item
curl -s -X POST "http://localhost:8100/dead-letters/JOB_ID/retry" | jq .

# Retry all DLQ items (after fixing root cause)
curl -s -X POST http://localhost:8100/dead-letters/retry-all | jq .

# Purge DLQ (permanently discard failed items)
curl -s -X DELETE http://localhost:8100/dead-letters | jq .
```

---

## 6. Runbook: Graph Store Corrupted (P3)

**Trigger**: GraphRAG queries return errors; `graphrag/stats` shows unexpected values; Neo4j connection errors.

### 6.1 Assess Neo4j State

```bash
# Can we connect?
curl -s http://localhost:8111/db/neo4j/cluster/available
# 200 = available, anything else = problem

# Check Neo4j container health
docker compose ps omnirag-neo4j
docker logs omnirag-neo4j --tail 50

# Check disk space
docker exec omnirag-neo4j df -h /data

# Check data integrity
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"CALL db.checkConsistency.full()"}]}' | jq .
```

### 6.2 Neo4j Won't Start

```bash
# Check logs for corruption messages
docker logs omnirag-neo4j 2>&1 | grep -i "corrupt\|error\|fatal" | tail -20

# If store files corrupted:
# 1. Stop Neo4j
docker compose stop omnirag-neo4j

# 2. Back up current data
docker exec omnirag-neo4j cp -r /data/databases/neo4j /data/databases/neo4j.bak

# 3. Remove corrupted store files
docker exec omnirag-neo4j rm -rf /data/databases/neo4j

# 4. Restart (creates fresh empty database)
docker compose start omnirag-neo4j
sleep 10

# 5. Rebuild graph from PostgreSQL
curl -s -X POST http://localhost:8100/graphrag/rebuild | jq .
```

### 6.3 Data Inconsistency (Graph Out of Sync)

```bash
# Compare entity counts between OmniRAG's view and Neo4j
APP_COUNT=$(curl -s http://localhost:8100/graphrag/stats | jq '.entity_count')
NEO4J_COUNT=$(curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (e:Entity) RETURN count(e)"}]}' | jq '.results[0].data[0].row[0]')
echo "App reports: $APP_COUNT, Neo4j has: $NEO4J_COUNT"

# If counts differ significantly:
# 1. Clear Neo4j
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (n) DETACH DELETE n"}]}'

# 2. Rebuild
curl -s -X POST http://localhost:8100/graphrag/rebuild | jq .

# 3. Monitor rebuild progress
watch -n 10 'curl -s http://localhost:8100/graphrag/stats | jq .'
```

### 6.4 Graph Queries Returning Errors

```bash
# Test each mode
for mode in local global drift; do
  echo "=== $mode ==="
  curl -s -X POST "http://localhost:8100/graphrag/query/$mode" \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}' | jq '{error: .error, detail: .detail}'
done

# If global mode fails: community reports missing
# Rebuild just reports (faster than full rebuild)
curl -s -X POST http://localhost:8100/graphrag/rebuild \
  -H "Content-Type: application/json" \
  -d '{"scope": "reports"}' | jq .

# If all modes fail: Neo4j connection issue
# Check OmniRAG's Neo4j connection config
docker exec omnirag-app env | grep NEO4J
```

---

## 7. Runbook: High Latency (P2)

**Trigger**: P95 search latency exceeds 10 seconds; user-reported slowness.

### 7.1 Identify the Bottleneck

```bash
# Current P95 latency from Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omnirag_search_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# Breakdown per phase from recent logs
docker logs omnirag-app --since 15m 2>&1 | jq '
  select(.event == "search.completed")
  | {
    total_s: .duration_seconds,
    embedding_ms: .embedding_latency_ms,
    vector_ms: .vector_latency_ms,
    bm25_ms: .bm25_latency_ms,
    rerank_ms: .rerank_latency_ms,
    generation_ms: .generation_latency_ms
  }' | tail -5
```

### 7.2 Cause: Redis Cache Cold/Down

```bash
# Check cache hit rate
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omnirag_cache_hits_total[5m]))/(sum(rate(omnirag_cache_hits_total[5m]))+sum(rate(omnirag_cache_misses_total[5m])))' | jq '.data.result[0].value[1]'

# If hit rate is 0 or very low:
redis-cli -p 8140 ping
redis-cli -p 8140 dbsize
redis-cli -p 8140 info memory | grep used_memory_human

# If Redis is down: restart
docker compose restart omnirag-redis
# App will reconnect automatically; cache will warm up over time

# If Redis is up but cache is empty (e.g., after restart):
# Cache will repopulate as queries come in. No manual action needed.
# To pre-warm: replay recent popular queries.
```

### 7.3 Cause: Qdrant Slow (Index Rebuilding)

```bash
# Check optimizer status
curl -s http://localhost:8120/collections/omnirag_chunks | jq '.result.optimizer_status'
# "ok" = idle
# If showing "indexing": HNSW index is being rebuilt. Queries use brute force (slow).

# Check segment count (too many segments = slow)
curl -s http://localhost:8120/collections/omnirag_chunks | jq '.result.segments_count'

# If segments > 10: trigger optimization
curl -s -X POST http://localhost:8120/collections/omnirag_chunks/optimize

# Wait for optimization to complete
watch -n 10 'curl -s http://localhost:8120/collections/omnirag_chunks | jq "{optimizer_status: .result.optimizer_status, segments: .result.segments_count}"'
```

### 7.4 Cause: Ollama LLM Slow

```bash
# Check if model is loaded in memory
curl -s http://localhost:8150/api/ps | jq '.models[] | {name, size_vram: .size_vram}'

# If empty: model needs cold-loading (first query will be slow)
# Pre-load the model:
curl -s -X POST http://localhost:8150/api/generate \
  -d '{"model": "llama3.2", "prompt": " ", "stream": false}' | jq '.total_duration'

# Check Ollama resource usage
docker stats omnirag-ollama --no-stream

# If GPU memory full with multiple models:
# Unload unused models (Ollama auto-evicts, but you can force it)
curl -s -X POST http://localhost:8150/api/generate \
  -d '{"model": "llama3.2", "keep_alive": 0}'
```

### 7.5 Cause: PostgreSQL Slow Queries

```bash
# Check for long-running queries
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT pid, now() - pg_stat_activity.query_start AS duration, left(query, 80)
   FROM pg_stat_activity
   WHERE state != 'idle' AND now() - pg_stat_activity.query_start > interval '5 seconds'
   ORDER BY duration DESC;"

# Kill a stuck query if needed
# psql -h localhost -p 8160 -U omnirag -d omnirag -c "SELECT pg_terminate_backend(PID_HERE);"

# Check connection pool exhaustion
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT count(*) AS total, state FROM pg_stat_activity GROUP BY state;"

# Check for missing indexes
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT relname, seq_scan, idx_scan
   FROM pg_stat_user_tables
   WHERE seq_scan > 1000 AND idx_scan = 0
   ORDER BY seq_scan DESC LIMIT 10;"
```

### 7.6 Cause: Embedding Generation Slow

```bash
# Check embedding latency
docker logs omnirag-app --since 15m 2>&1 | jq 'select(.event == "embedding.generation_complete") | .latency_ms' | sort -n

# If consistently > 500ms per batch:
# 1. Check if Ollama is using GPU
docker exec omnirag-ollama ollama ps

# 2. Try reducing batch size in OmniRAG config
# 3. Check if embedding model is appropriate (large models = slow)
curl -s http://localhost:8150/api/tags | jq '.models[] | select(.name | contains("embed")) | {name, parameter_size: .details.parameter_size}'
```

---

## 8. Post-Incident

### Post-Mortem Template

Use this template within 48 hours of any P1 or P2 incident:

```markdown
# Post-Mortem: [INCIDENT TITLE]

**Date**: YYYY-MM-DD
**Duration**: HH:MM (start) - HH:MM (resolved)
**Severity**: P1/P2
**Author**: [name]

## Summary

[1-2 sentence summary of what happened and the impact]

## Timeline (UTC)

| Time | Event |
|---|---|
| HH:MM | Alert fired: [alert name] |
| HH:MM | Responder acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Service restored |
| HH:MM | Monitoring confirmed recovery |

## Impact

- **Users affected**: [number or percentage]
- **Queries failed**: [count]
- **Intake jobs lost/delayed**: [count]
- **Data loss**: [yes/no, details]
- **SLA impact**: [yes/no, details]

## Root Cause

[Detailed technical explanation of what failed and why]

## Detection

- **How detected**: [alert / user report / monitoring]
- **Time to detect**: [minutes]
- **Detection gap**: [what should have caught this sooner?]

## Resolution

[Step-by-step what was done to fix it]

## Action Items

| # | Action | Owner | Priority | Due Date |
|---|---|---|---|---|
| 1 | [action] | [owner] | P1/P2/P3 | YYYY-MM-DD |
| 2 | [action] | [owner] | P1/P2/P3 | YYYY-MM-DD |

## Lessons Learned

- **What went well**: [things that worked during response]
- **What went poorly**: [things that slowed down response]
- **Where we got lucky**: [things that could have made it worse]
```

### Post-Incident Verification Checklist

After any incident, verify these before declaring resolution:

```bash
# 1. Application health
curl -s http://localhost:8100/health | jq '.status'
# Expected: "healthy"

# 2. All backing services up
curl -s http://localhost:8100/health | jq '.components | to_entries[] | select(.value != "up")'
# Expected: empty output

# 3. No open circuit breakers
curl -s http://localhost:8100/backpressure/circuit-breakers | jq '.breakers | to_entries[] | select(.value.state != "closed")'
# Expected: empty output

# 4. DLQ not growing
DLQ1=$(curl -s http://localhost:8100/dead-letters | jq '.count')
sleep 60
DLQ2=$(curl -s http://localhost:8100/dead-letters | jq '.count')
echo "DLQ: $DLQ1 → $DLQ2 (should be stable or decreasing)"

# 5. Error rate normalized
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omnirag_http_requests_total{status=~"5.."}[5m]))/sum(rate(omnirag_http_requests_total[5m]))' | jq '.data.result[0].value[1]'
# Expected: < 0.01

# 6. Search latency normalized
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omnirag_search_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'
# Expected: < 5

# 7. Intake pipeline flowing
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT state, count(*) FROM intake_jobs WHERE state NOT IN ('ACTIVE', 'FAILED') GROUP BY state;"
# Expected: no stuck jobs (or counts decreasing over time)

# 8. End-to-end search test
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query after incident", "top_k": 3}' | jq '.results | length'
# Expected: > 0 (if documents exist)
```

---

## 9. Escalation Path

### When to Escalate

| Condition | Escalate To |
|---|---|
| P1 not resolved within 30 minutes | Engineering lead + on-call manager |
| P2 not resolved within 2 hours | Engineering lead |
| Data loss confirmed | Engineering lead + product manager |
| Security incident (unauthorized access) | Security team immediately |
| Multiple simultaneous P1/P2 incidents | Incident commander + all available engineers |
| PostgreSQL data corruption | DBA / database specialist |
| Infrastructure failure (host, network) | Infrastructure / platform team |

### Escalation Steps

1. **Notify**: Post in `#incidents` channel with severity, impact, and current status
2. **Bridge**: Start a video/voice call for P1 incidents
3. **Handoff**: If handing off to another responder, provide:
   - Current hypothesis
   - What has been tried
   - What logs/metrics are relevant
   - Any commands that have been run (and their output)
4. **Status updates**: Every 15 minutes for P1, every 30 minutes for P2

### Contact List

| Role | Responsibility |
|---|---|
| **On-Call SRE** | First responder for all alerts; owns triage and initial response |
| **Backend Engineer** | Intake pipeline, embedding, retrieval, GraphRAG internals |
| **Infrastructure Engineer** | Docker, networking, backing services (PG, Neo4j, Qdrant, ES, Redis) |
| **ML Engineer** | Embedding models, reranker, router classifier, Ollama configuration |
| **Engineering Lead** | Escalation point; coordinates cross-team response |
| **Product Manager** | User communication; impact assessment |

### Communication Templates

**Initial Notification (P1)**:
> INCIDENT: OmniRAG service unavailable. Impact: All search and ingestion requests failing. Started: HH:MM UTC. Investigating. Next update in 15 minutes.

**Status Update**:
> UPDATE: Root cause identified as [cause]. Fix in progress: [what is being done]. ETA to resolution: [estimate]. Impact: [ongoing impact].

**Resolution**:
> RESOLVED: OmniRAG service restored at HH:MM UTC. Total duration: X minutes. Root cause: [brief explanation]. Post-mortem scheduled for [date].
