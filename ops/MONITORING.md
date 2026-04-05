# OmniRAG Monitoring Runbook

## 1. Health Checks

### Application Health

```bash
# Primary health check — returns JSON with component status
curl -s http://localhost:8100/health | jq .

# Expected response (healthy):
# {
#   "status": "healthy",
#   "components": {
#     "postgresql": "up",
#     "neo4j": "up",
#     "qdrant": "up",
#     "elasticsearch": "up",
#     "redis": "up",
#     "ollama": "up"
#   }
# }

# Backpressure subsystem health
curl -s http://localhost:8100/backpressure/health | jq .

# Circuit breaker states (should all be "closed")
curl -s http://localhost:8100/backpressure/circuit-breakers | jq .

# Dead letter queue (should be empty or near-empty)
curl -s http://localhost:8100/dead-letters | jq '.count'
```

### Alerting Thresholds

| Check | Interval | Warning | Critical |
|---|---|---|---|
| `/health` returns non-200 | 15s | 2 consecutive failures | 4 consecutive failures |
| Any component `"down"` | 30s | 1 failure | 3 consecutive failures |
| `/backpressure/health` degraded | 30s | `status: "degraded"` | `status: "critical"` |
| Circuit breaker open | 30s | 1 breaker open | 2+ breakers open |
| Dead letter queue depth | 60s | > 10 items | > 50 items |
| Response time `/health` | 15s | > 2s | > 5s |

### Synthetic Probes

Run these every 5 minutes to verify end-to-end functionality:

```bash
# Search probe — should return results if any documents are ingested
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "health check probe", "top_k": 1}' | jq '.results | length'

# GraphRAG probe — should return stats without error
curl -s http://localhost:8100/graphrag/stats | jq '.entity_count'
```

---

## 2. Prometheus Metrics

Metrics are exposed at `GET /metrics` in Prometheus exposition format.

### Key Metrics to Dashboard

#### Request Metrics

| Metric | Type | Description |
|---|---|---|
| `omnirag_http_requests_total` | Counter | Total HTTP requests by method, endpoint, status |
| `omnirag_http_request_duration_seconds` | Histogram | Request latency by endpoint |
| `omnirag_search_requests_total` | Counter | Search requests by mode (hybrid, vector, bm25) |
| `omnirag_search_latency_seconds` | Histogram | End-to-end search latency |

#### Intake Pipeline

| Metric | Type | Description |
|---|---|---|
| `omnirag_intake_jobs_total` | Counter | Jobs submitted by status (registered, active, failed) |
| `omnirag_intake_jobs_in_progress` | Gauge | Currently processing intake jobs |
| `omnirag_intake_state_transitions_total` | Counter | State transitions by from_state, to_state |
| `omnirag_intake_duration_seconds` | Histogram | Time from REGISTERED to ACTIVE |
| `omnirag_intake_queue_depth` | Gauge | Jobs waiting in each state |

#### Embedding & Retrieval

| Metric | Type | Description |
|---|---|---|
| `omnirag_embedding_requests_total` | Counter | Embedding generation requests |
| `omnirag_embedding_latency_seconds` | Histogram | Embedding generation latency |
| `omnirag_embedding_tokens_total` | Counter | Total tokens embedded |
| `omnirag_retrieval_results_total` | Counter | Retrieved chunks by source (vector, bm25) |
| `omnirag_reranker_latency_seconds` | Histogram | Reranker processing time |
| `omnirag_rrf_fusion_latency_seconds` | Histogram | RRF fusion processing time |

#### Graph

| Metric | Type | Description |
|---|---|---|
| `omnirag_graph_query_latency_seconds` | Histogram | GraphRAG query latency by mode |
| `omnirag_graph_entities_total` | Gauge | Total entities in graph |
| `omnirag_graph_communities_total` | Gauge | Total communities detected |
| `omnirag_entity_extraction_latency_seconds` | Histogram | Entity extraction time per document |

#### Cache

| Metric | Type | Description |
|---|---|---|
| `omnirag_cache_hits_total` | Counter | Cache hits by cache_name |
| `omnirag_cache_misses_total` | Counter | Cache misses by cache_name |
| `omnirag_cache_evictions_total` | Counter | Cache evictions |

#### Backpressure

| Metric | Type | Description |
|---|---|---|
| `omnirag_backpressure_rejected_total` | Counter | Requests rejected by backpressure |
| `omnirag_circuit_breaker_state` | Gauge | 0=closed, 1=half-open, 2=open |
| `omnirag_token_bucket_available` | Gauge | Available tokens in rate limiter |
| `omnirag_dead_letter_queue_depth` | Gauge | Items in DLQ |

#### Backing Services

| Metric | Type | Description |
|---|---|---|
| `omnirag_db_connection_pool_active` | Gauge | Active PostgreSQL connections |
| `omnirag_db_connection_pool_idle` | Gauge | Idle PostgreSQL connections |
| `omnirag_db_query_duration_seconds` | Histogram | Database query latency |
| `omnirag_ollama_inference_latency_seconds` | Histogram | LLM inference latency |
| `omnirag_ollama_tokens_per_second` | Gauge | LLM generation throughput |

---

## 3. Grafana Dashboard Setup

### Dashboard: OmniRAG Overview

Import these panels into a single Grafana dashboard.

#### Panel 1: Request Rate (Graph)

```promql
# Requests per second by endpoint
rate(omnirag_http_requests_total[5m])
```

Legend: `{{method}} {{endpoint}} {{status}}`

#### Panel 2: Error Rate (Graph)

```promql
# 5xx error rate as percentage
100 * sum(rate(omnirag_http_requests_total{status=~"5.."}[5m]))
  / sum(rate(omnirag_http_requests_total[5m]))
```

Threshold: Warning at 1%, Critical at 5%.

#### Panel 3: Search Latency P50/P95/P99 (Graph)

```promql
# P50
histogram_quantile(0.50, sum(rate(omnirag_search_latency_seconds_bucket[5m])) by (le))
# P95
histogram_quantile(0.95, sum(rate(omnirag_search_latency_seconds_bucket[5m])) by (le))
# P99
histogram_quantile(0.99, sum(rate(omnirag_search_latency_seconds_bucket[5m])) by (le))
```

#### Panel 4: Intake Pipeline Funnel (Stat)

```promql
# Jobs by current state
omnirag_intake_queue_depth
```

Display as bar gauge, one bar per state label.

#### Panel 5: Cache Hit Ratio (Gauge)

```promql
sum(rate(omnirag_cache_hits_total[5m]))
  / (sum(rate(omnirag_cache_hits_total[5m])) + sum(rate(omnirag_cache_misses_total[5m])))
```

Thresholds: Green > 0.7, Yellow > 0.4, Red < 0.4.

#### Panel 6: Embedding Throughput (Graph)

```promql
rate(omnirag_embedding_tokens_total[5m])
```

#### Panel 7: Graph Query Latency by Mode (Graph)

```promql
histogram_quantile(0.95, sum(rate(omnirag_graph_query_latency_seconds_bucket[5m])) by (le, mode))
```

Legend: `{{mode}} P95`

#### Panel 8: Circuit Breaker Status (Stat)

```promql
omnirag_circuit_breaker_state
```

Value mapping: 0 = "CLOSED" (green), 1 = "HALF-OPEN" (yellow), 2 = "OPEN" (red).

#### Panel 9: Dead Letter Queue Depth (Graph)

```promql
omnirag_dead_letter_queue_depth
```

Threshold: Warning at 10, Critical at 50.

#### Panel 10: Backing Service Latency (Graph)

```promql
# PostgreSQL query latency P95
histogram_quantile(0.95, sum(rate(omnirag_db_query_duration_seconds_bucket[5m])) by (le))

# LLM inference latency P95
histogram_quantile(0.95, sum(rate(omnirag_ollama_inference_latency_seconds_bucket[5m])) by (le))
```

#### Panel 11: Connection Pool Utilization (Gauge)

```promql
omnirag_db_connection_pool_active
  / (omnirag_db_connection_pool_active + omnirag_db_connection_pool_idle)
```

Thresholds: Green < 0.7, Yellow < 0.9, Red >= 0.9.

#### Panel 12: Backpressure Rejections (Graph)

```promql
rate(omnirag_backpressure_rejected_total[5m])
```

### Dashboard JSON Template

Save this as a starting point for Grafana provisioning:

```json
{
  "dashboard": {
    "title": "OmniRAG Production",
    "tags": ["omnirag", "production"],
    "timezone": "utc",
    "refresh": "30s",
    "time": { "from": "now-1h", "to": "now" }
  }
}
```

---

## 4. Log Analysis

OmniRAG uses `structlog` with JSON output. All log entries have these base fields:

```json
{
  "timestamp": "2026-04-05T12:00:00Z",
  "level": "info",
  "event": "event_name",
  "logger": "module.name",
  "request_id": "uuid",
  "trace_id": "otel-trace-id"
}
```

### Key Log Events to Watch

| Event | Level | Meaning | Action |
|---|---|---|---|
| `intake.state_transition` | info | Job moved between states | Normal; watch for stuck states |
| `intake.job_failed` | error | Intake job failed | Check `error` field, may need re-ingest |
| `intake.job_deferred` | warning | Job deferred by backpressure | Monitor backpressure health |
| `search.query_routed` | info | Query routed to strategy | Check `route` field for unexpected BASIC routing |
| `search.no_results` | warning | Search returned empty | Check index health |
| `embedding.generation_failed` | error | Embedding request failed | Check Ollama/model availability |
| `graph.entity_extraction_failed` | error | Entity extraction failed | Check spaCy model, LLM |
| `graph.community_detection_complete` | info | Louvain/Leiden finished | Check community_count for sanity |
| `circuit_breaker.opened` | error | Circuit breaker tripped | Investigate underlying service |
| `circuit_breaker.half_open` | warning | Circuit breaker testing recovery | Service may be recovering |
| `circuit_breaker.closed` | info | Circuit breaker recovered | Service is healthy again |
| `dead_letter.enqueued` | warning | Failed item moved to DLQ | Investigate root cause |
| `backpressure.admission_rejected` | warning | Request rejected at admission | System under load |
| `db.connection_error` | error | PostgreSQL connection failed | Check pg_isready |
| `redis.connection_error` | error | Redis connection failed | Check redis-cli ping |
| `ollama.inference_timeout` | error | LLM inference exceeded timeout | Check Ollama load, model size |

### Common Log Queries

Using `jq` against JSON log files or piped from `docker logs`:

```bash
# All errors in the last hour
docker logs omnirag-app --since 1h 2>&1 | jq -r 'select(.level == "error") | "\(.timestamp) \(.event): \(.error // .message // "")"'

# Intake failures
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.event == "intake.job_failed")'

# Circuit breaker events
docker logs omnirag-app --since 6h 2>&1 | jq 'select(.event | startswith("circuit_breaker"))'

# Slow searches (> 5s)
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.event == "search.completed" and .duration_seconds > 5)'

# Trace a specific request across logs
docker logs omnirag-app --since 1h 2>&1 | jq 'select(.request_id == "REQUEST_UUID_HERE")'

# Dead letter queue additions
docker logs omnirag-app --since 24h 2>&1 | jq 'select(.event == "dead_letter.enqueued") | {timestamp, job_id, error}'

# Count events by type
docker logs omnirag-app --since 1h 2>&1 | jq -r '.event' | sort | uniq -c | sort -rn | head -20
```

---

## 5. Backing Service Health

### PostgreSQL (port 8160)

```bash
# Quick health check
pg_isready -h localhost -p 8160

# Connection count
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"

# Check for long-running queries (> 30s)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state != 'idle' AND now() - pg_stat_activity.query_start > interval '30 seconds'
   ORDER BY duration DESC;"

# Table sizes (intake state table)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
   FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Dead tuples (need vacuum?)
psql -h localhost -p 8160 -U omnirag -d omnirag -c \
  "SELECT schemaname, relname, n_dead_tup, last_autovacuum
   FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY n_dead_tup DESC;"
```

### Neo4j (port 8110 bolt / 8111 HTTP)

```bash
# HTTP health check
curl -s http://localhost:8111/db/neo4j/cluster/available

# Basic connectivity via Cypher HTTP API
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"RETURN 1 AS alive"}]}' | jq .

# Entity count
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (n) RETURN count(n) AS node_count"}]}' | jq '.results[0].data[0].row[0]'

# Relationship count
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH ()-[r]->() RETURN count(r) AS rel_count"}]}' | jq '.results[0].data[0].row[0]'

# Check for unindexed queries (slow queries)
curl -s -X POST http://localhost:8111/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"CALL db.indexes() YIELD name, state RETURN name, state"}]}' | jq '.results[0].data'
```

### Qdrant (port 8120 HTTP / 8121 gRPC)

```bash
# Health check
curl -s http://localhost:8120/healthz

# Cluster info
curl -s http://localhost:8120/cluster | jq .

# List collections
curl -s http://localhost:8120/collections | jq '.result.collections[].name'

# Collection details (point count, index status)
curl -s http://localhost:8120/collections/omnirag_chunks | jq '{
  points_count: .result.points_count,
  indexed_vectors_count: .result.indexed_vectors_count,
  status: .result.status
}'

# Check if collection is being optimized (heavy load indicator)
curl -s http://localhost:8120/collections/omnirag_chunks | jq '.result.optimizer_status'
```

### Elasticsearch (port 8130)

```bash
# Cluster health
curl -s http://localhost:8130/_cluster/health | jq '{status, number_of_nodes, active_shards, relocating_shards, unassigned_shards}'

# Index stats
curl -s http://localhost:8130/_cat/indices?v

# Document count in main index
curl -s http://localhost:8130/omnirag_documents/_count | jq '.count'

# Check for red/yellow shards
curl -s http://localhost:8130/_cat/shards?v | grep -E "UNASSIGNED|RELOCATING"

# Pending tasks
curl -s http://localhost:8130/_cluster/pending_tasks | jq '.tasks | length'
```

### Redis (port 8140)

```bash
# Ping
redis-cli -p 8140 ping
# Expected: PONG

# Info overview
redis-cli -p 8140 info server | head -10

# Memory usage
redis-cli -p 8140 info memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# Connected clients
redis-cli -p 8140 info clients | grep connected_clients

# Key count by pattern
redis-cli -p 8140 info keyspace

# Check rate limiter keys
redis-cli -p 8140 keys "ratelimit:*" | wc -l

# Check cache keys
redis-cli -p 8140 keys "cache:*" | wc -l

# Slow log (queries slower than 10ms)
redis-cli -p 8140 slowlog get 10
```

### Ollama (port 8150)

```bash
# Health check
curl -s http://localhost:8150/api/tags | jq '.models[].name'

# Check if specific model is loaded
curl -s http://localhost:8150/api/tags | jq '.models[] | select(.name | contains("llama")) | {name, size}'

# Check running models (loaded in memory)
curl -s http://localhost:8150/api/ps | jq '.models[].name'

# Quick inference test
curl -s -X POST http://localhost:8150/api/generate \
  -d '{"model": "llama3.2", "prompt": "ping", "stream": false}' | jq '{model, total_duration, eval_count}'
```

---

## 6. Alerting Rules

Save as `omnirag_alerts.yml` for Prometheus Alertmanager:

```yaml
groups:
  - name: omnirag.critical
    rules:
      - alert: OmniRAGDown
        expr: up{job="omnirag"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OmniRAG application is down"
          description: "The OmniRAG application on {{ $labels.instance }} has been unreachable for 1 minute."

      - alert: OmniRAGHighErrorRate
        expr: |
          sum(rate(omnirag_http_requests_total{status=~"5.."}[5m]))
            / sum(rate(omnirag_http_requests_total[5m])) > 0.05
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "OmniRAG error rate above 5%"
          description: "HTTP 5xx error rate is {{ $value | humanizePercentage }} over the last 5 minutes."

      - alert: OmniRAGAllCircuitBreakersOpen
        expr: count(omnirag_circuit_breaker_state == 2) >= 2
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Multiple circuit breakers are open"
          description: "{{ $value }} circuit breakers are in OPEN state. Service is severely degraded."

  - name: omnirag.warning
    rules:
      - alert: OmniRAGHighLatency
        expr: |
          histogram_quantile(0.95, sum(rate(omnirag_search_latency_seconds_bucket[5m])) by (le)) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "OmniRAG search P95 latency above 10s"
          description: "P95 search latency is {{ $value }}s."

      - alert: OmniRAGCircuitBreakerOpen
        expr: omnirag_circuit_breaker_state == 2
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker {{ $labels.breaker }} is OPEN"
          description: "Circuit breaker {{ $labels.breaker }} has been open for 2 minutes."

      - alert: OmniRAGDLQGrowing
        expr: omnirag_dead_letter_queue_depth > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dead letter queue has {{ $value }} items"
          description: "DLQ depth is {{ $value }}. Items are failing processing."

      - alert: OmniRAGBackpressureActive
        expr: rate(omnirag_backpressure_rejected_total[5m]) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "OmniRAG is rejecting requests due to backpressure"
          description: "{{ $value }} requests/s are being rejected."

      - alert: OmniRAGLowCacheHitRate
        expr: |
          sum(rate(omnirag_cache_hits_total[10m]))
            / (sum(rate(omnirag_cache_hits_total[10m])) + sum(rate(omnirag_cache_misses_total[10m]))) < 0.3
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate below 30%"
          description: "Cache hit ratio is {{ $value | humanizePercentage }}. Check Redis and cache configuration."

      - alert: OmniRAGIntakeStalled
        expr: omnirag_intake_jobs_in_progress > 0 and rate(omnirag_intake_state_transitions_total[10m]) == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Intake pipeline appears stalled"
          description: "Jobs are in progress but no state transitions have occurred in 10 minutes."

  - name: omnirag.backing_services
    rules:
      - alert: PostgreSQLDown
        expr: pg_up{job="omnirag-postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is down"

      - alert: Neo4jDown
        expr: up{job="omnirag-neo4j"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Neo4j is down"

      - alert: QdrantDown
        expr: up{job="omnirag-qdrant"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Qdrant vector DB is down"

      - alert: ElasticsearchDown
        expr: up{job="omnirag-elasticsearch"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Elasticsearch is down"

      - alert: ElasticsearchYellow
        expr: elasticsearch_cluster_health_status{color="yellow"} == 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Elasticsearch cluster is yellow"

      - alert: RedisDown
        expr: up{job="omnirag-redis"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis is down"

      - alert: RedisHighMemory
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory usage above 85%"

      - alert: OllamaDown
        expr: up{job="omnirag-ollama"} == 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Ollama LLM service is down"
          description: "LLM inference is unavailable. Embedding and generation will fail."

      - alert: PostgreSQLConnectionPoolExhausted
        expr: |
          omnirag_db_connection_pool_active
            / (omnirag_db_connection_pool_active + omnirag_db_connection_pool_idle) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL connection pool is 90% utilized"
```

### Prometheus Scrape Config

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "omnirag"
    scrape_interval: 15s
    static_configs:
      - targets: ["localhost:8100"]
    metrics_path: /metrics
```
