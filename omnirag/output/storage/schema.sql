-- OmniRAG Output Layer — PostgreSQL Storage Schema

-- Chunk metadata (output-side, with embedding status)
CREATE TABLE IF NOT EXISTS output_chunks (
    chunk_id UUID PRIMARY KEY,
    doc_id UUID NOT NULL,
    content_hash TEXT NOT NULL,
    acl_principals TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    embedding_status TEXT DEFAULT 'pending'
        CHECK (embedding_status IN ('pending', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS output_documents (
    doc_id UUID PRIMARY KEY,
    source_uri TEXT NOT NULL,
    semantic_type VARCHAR(32),
    title TEXT,
    ingestion_ts TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS output_lineage_edges (
    chunk_id UUID REFERENCES output_chunks(chunk_id) ON DELETE CASCADE,
    parent_uri TEXT NOT NULL,
    transformation TEXT,
    PRIMARY KEY (chunk_id, parent_uri)
);

-- Webhook registrations
CREATE TABLE IF NOT EXISTS webhook_registrations (
    id VARCHAR(16) PRIMARY KEY,
    url TEXT NOT NULL,
    events TEXT[] NOT NULL DEFAULT '{}',
    secret TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Webhook delivery log
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id VARCHAR(16) REFERENCES webhook_registrations(id),
    event_type VARCHAR(32),
    status VARCHAR(16),
    attempt INT DEFAULT 1,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Answer logs (for lineage/answer endpoint)
CREATE TABLE IF NOT EXISTS answer_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash TEXT NOT NULL,
    user_principal_hash TEXT,
    answer_hash TEXT,
    chunk_ids UUID[] NOT NULL DEFAULT '{}',
    mode VARCHAR(16),
    latency_ms FLOAT,
    status_code INT DEFAULT 200,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rate limit overrides
CREATE TABLE IF NOT EXISTS rate_limit_overrides (
    principal TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_output_chunks_acl ON output_chunks USING GIN (acl_principals);
CREATE INDEX IF NOT EXISTS idx_output_chunks_doc ON output_chunks (doc_id);
CREATE INDEX IF NOT EXISTS idx_output_chunks_status ON output_chunks (embedding_status);
CREATE INDEX IF NOT EXISTS idx_answer_logs_user ON answer_logs (user_principal_hash);
CREATE INDEX IF NOT EXISTS idx_answer_logs_time ON answer_logs (created_at);

-- Stored procedure: ACL-aware chunk lookup
CREATE OR REPLACE FUNCTION get_visible_chunks(user_principals TEXT[])
RETURNS TABLE (chunk_id UUID, doc_id UUID, content_hash TEXT, metadata JSONB)
LANGUAGE SQL
AS $$
    SELECT chunk_id, doc_id, content_hash, metadata
    FROM output_chunks
    WHERE acl_principals && user_principals;
$$;
