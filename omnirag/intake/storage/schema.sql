-- OmniRAG Intake Gate — PostgreSQL Storage Schema
-- 12 tables for full governed intake control plane

CREATE TABLE IF NOT EXISTS connectors (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    source_type VARCHAR(32) NOT NULL,
    auth_ref VARCHAR(256),
    capabilities JSONB DEFAULT '{}',
    rate_limits JSONB DEFAULT '{}',
    backpressure_config JSONB DEFAULT '{}',
    bulk_import_config JSONB,
    policy_profile_id VARCHAR(64),
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id VARCHAR(64) PRIMARY KEY,
    connector_id VARCHAR(64) NOT NULL,
    trigger VARCHAR(16) NOT NULL DEFAULT 'manual',
    state VARCHAR(32) NOT NULL DEFAULT 'registered',
    attempt INT DEFAULT 0,
    cursor_key VARCHAR(256),
    source TEXT,
    config JSONB DEFAULT '{}',
    pipeline VARCHAR(64),
    source_object_ids JSONB DEFAULT '[]',
    error_message TEXT,
    errors JSONB DEFAULT '[]',
    deferred_until TIMESTAMP,
    files_found INT DEFAULT 0,
    files_loaded INT DEFAULT 0,
    documents_created INT DEFAULT 0,
    chunks_created INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_cursors (
    connector_id VARCHAR(64) PRIMARY KEY,
    cursor_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_objects (
    id UUID PRIMARY KEY,
    connector_id VARCHAR(64) NOT NULL,
    external_id VARCHAR(512) NOT NULL,
    object_kind VARCHAR(16) NOT NULL DEFAULT 'blob',
    mime_type VARCHAR(64),
    checksum VARCHAR(64),
    version_ref VARCHAR(256),
    parent_ref VARCHAR(512),
    source_url TEXT,
    timestamps JSONB DEFAULT '{}',
    acl_snapshot_ref UUID,
    raw_ref TEXT,
    metadata JSONB DEFAULT '{}',
    UNIQUE(connector_id, external_id, version_ref)
);

CREATE TABLE IF NOT EXISTS canonical_documents (
    id UUID PRIMARY KEY,
    source_object_ref UUID REFERENCES source_objects(id),
    semantic_type VARCHAR(32) NOT NULL,
    title TEXT,
    language VARCHAR(8),
    body TEXT,
    structure JSONB,
    metadata JSONB DEFAULT '{}',
    provenance JSONB DEFAULT '{}',
    acl JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES canonical_documents(id),
    text TEXT NOT NULL,
    "order" INT NOT NULL DEFAULT 0,
    section_path TEXT[],
    metadata JSONB DEFAULT '{}',
    acl_filter_ref UUID,
    embedding_ref TEXT,
    chunk_type VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS acl_snapshots (
    id UUID PRIMARY KEY,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dead_letters (
    id UUID PRIMARY KEY,
    job_id VARCHAR(64),
    connector_id VARCHAR(64),
    error TEXT,
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tombstones (
    id UUID PRIMARY KEY,
    source_object_ref UUID,
    connector_id VARCHAR(64),
    reason VARCHAR(64) DEFAULT 'deleted',
    deleted_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lineage_events (
    id UUID PRIMARY KEY,
    job_id VARCHAR(64),
    source_object_id UUID,
    document_id UUID,
    event_type VARCHAR(32),
    from_state VARCHAR(32),
    to_state VARCHAR(32),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backpressure_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indexer_id VARCHAR(64),
    event_type VARCHAR(32),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS indexer_health_snapshots (
    indexer_id VARCHAR(64),
    queue_depth INT,
    avg_latency_ms FLOAT,
    error_rate FLOAT,
    status VARCHAR(16),
    recorded_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (indexer_id, recorded_at)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sync_jobs_connector ON sync_jobs(connector_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_state ON sync_jobs(state);
CREATE INDEX IF NOT EXISTS idx_source_objects_connector ON source_objects(connector_id);
CREATE INDEX IF NOT EXISTS idx_canonical_documents_semantic ON canonical_documents(semantic_type);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_lineage_job ON lineage_events(job_id);
CREATE INDEX IF NOT EXISTS idx_tombstones_connector ON tombstones(connector_id);
