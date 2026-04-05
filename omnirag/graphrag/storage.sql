-- OmniGraph — Additional PostgreSQL tables (merged from spec)

-- Entity full-text search
CREATE TABLE IF NOT EXISTS entity_search (
    entity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT[],
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', name || ' ' || COALESCE(array_to_string(aliases, ' '), ''))) STORED
);
CREATE INDEX IF NOT EXISTS idx_entity_search_fts ON entity_search USING GIN (fts);

-- Graph build jobs
CREATE TABLE IF NOT EXISTS graph_build_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_run_id UUID,
    status VARCHAR(20) DEFAULT 'pending',
    node_count INT DEFAULT 0,
    edge_count INT DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Community computation runs
CREATE TABLE IF NOT EXISTS community_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_version INT,
    leiden_resolutions FLOAT[],
    community_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Query traces (AnswerTrace)
CREATE TABLE IF NOT EXISTS query_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    answer_id UUID,
    query_text TEXT,
    selected_mode VARCHAR(20),
    router_stage1_rule TEXT,
    router_stage2_bert_score FLOAT,
    router_stage3_override_reason TEXT,
    context_bundle JSONB,
    llm_model VARCHAR(50),
    token_input INT DEFAULT 0,
    token_output INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    cache_hit BOOLEAN DEFAULT FALSE,
    acl_filtered_nodes INT DEFAULT 0,
    user_roles TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_query_traces_mode ON query_traces (selected_mode);
CREATE INDEX IF NOT EXISTS idx_query_traces_time ON query_traces (created_at);

-- ACL authoritative source (node-level)
CREATE TABLE IF NOT EXISTS node_acls (
    node_id UUID PRIMARY KEY,
    node_type VARCHAR(10) CHECK (node_type IN ('entity', 'relation', 'community')),
    read_roles TEXT[] NOT NULL DEFAULT '{}',
    write_roles TEXT[] NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cache invalidation log
CREATE TABLE IF NOT EXISTS cache_invalidation_log (
    id SERIAL PRIMARY KEY,
    pattern TEXT,
    reason TEXT,
    invalidated_keys INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Metric events (Prometheus replay)
CREATE TABLE IF NOT EXISTS metric_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION DEFAULT 0,
    labels JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_metric_events_name ON metric_events (name);

-- LLM judge evaluations
CREATE TABLE IF NOT EXISTS evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_trace_id UUID,
    score FLOAT DEFAULT 0,
    evaluator_model VARCHAR(50),
    feedback TEXT,
    dimensions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent/workflow runs
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_type VARCHAR(32),
    status VARCHAR(16) DEFAULT 'pending',
    steps JSONB DEFAULT '[]',
    final_output JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
