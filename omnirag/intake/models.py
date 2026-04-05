"""Intake data models — governed control plane contracts.

Based on: RAG Intake Gate Document + References Document.
Three-layer normalization: SourceObject → CanonicalDocument → Chunk
Three transport types: BlobAsset, RecordAsset, EventAsset
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ─── Enums ───

class ObjectKind(str, Enum):
    BLOB = "blob"
    RECORD = "record"
    EVENT = "event"


class SemanticType(str, Enum):
    DOCUMENT = "document"
    TABLE = "table"
    CODE = "code"
    CONVERSATION = "conversation"
    EMAIL = "email"
    WEBPAGE = "webpage"
    NOTEBOOK = "notebook"
    EVENT_WINDOW = "event_window"
    TICKET = "ticket"


class Visibility(str, Enum):
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"
    TENANT = "tenant"


class JobState(str, Enum):
    # Active states (12)
    REGISTERED = "registered"
    DISCOVERED = "discovered"
    AUTHORIZED = "authorized"
    FETCHED = "fetched"
    EXTRACTED = "extracted"
    MATERIALIZED = "materialized"
    ENRICHED = "enriched"
    ACL_BOUND = "acl_bound"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    VERIFIED = "verified"
    ACTIVE = "active"
    # Terminal / exception states (5)
    DEFERRED = "deferred"
    FAILED = "failed"
    TOMBSTONED = "tombstoned"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"
    # Dead letter
    DEAD_LETTERED = "dead_lettered"


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    STREAM = "stream"
    API = "api"


class IndexerStatus(str, Enum):
    HEALTHY = "healthy"
    BACKLOGGED = "backlogged"
    CRITICAL = "critical"


class BackpressureMode(str, Enum):
    QUEUE = "queue"
    THROTTLE = "throttle"
    SKIP = "skip"


class BulkStrategy(str, Enum):
    SHARDED = "sharded"
    INCREMENTAL = "incremental"
    DEFERRED = "deferred"


# ─── ACL ───

@dataclass
class ACL:
    """Access control list — captured at ingest, propagated to chunks."""
    principals: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    visibility: Visibility = Visibility.TENANT
    source_scope: str | None = None

    def to_dict(self) -> dict:
        return {
            "principals": self.principals,
            "groups": self.groups,
            "visibility": self.visibility.value,
            "source_scope": self.source_scope,
        }


# ─── Connector Config ───

@dataclass
class RateLimits:
    docs_per_minute: int = 100
    chunks_per_second: int = 50
    concurrent_fetchers: int = 4
    batch_size: int = 100


@dataclass
class BackpressureConfig:
    mode: BackpressureMode = BackpressureMode.QUEUE
    max_queue_depth: int = 1000
    cooldown_seconds: int = 10


@dataclass
class BulkImportConfig:
    strategy: BulkStrategy = BulkStrategy.INCREMENTAL
    shard_count: int = 4
    priority: str = "normal"


@dataclass
class ConnectorCapabilities:
    full_sync: bool = True
    incremental_sync: bool = False
    webhooks: bool = False
    acl_read: bool = False
    versioning: bool = False
    attachments: bool = False


@dataclass
class ConnectorConfig:
    """Full connector configuration with rate limits and backpressure."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    source_type: str = ""
    auth_ref: str | None = None
    capabilities: ConnectorCapabilities = field(default_factory=ConnectorCapabilities)
    policy_profile_id: str | None = None
    rate_limits: RateLimits = field(default_factory=RateLimits)
    backpressure: BackpressureConfig = field(default_factory=BackpressureConfig)
    bulk_import: BulkImportConfig | None = None
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "source_type": self.source_type,
            "status": self.status,
            "capabilities": {
                "full_sync": self.capabilities.full_sync,
                "incremental_sync": self.capabilities.incremental_sync,
                "webhooks": self.capabilities.webhooks,
                "acl_read": self.capabilities.acl_read,
            },
            "rate_limits": {
                "docs_per_minute": self.rate_limits.docs_per_minute,
                "chunks_per_second": self.rate_limits.chunks_per_second,
                "concurrent_fetchers": self.rate_limits.concurrent_fetchers,
                "batch_size": self.rate_limits.batch_size,
            },
            "backpressure": {
                "mode": self.backpressure.mode.value,
                "max_queue_depth": self.backpressure.max_queue_depth,
                "cooldown_seconds": self.backpressure.cooldown_seconds,
            },
        }


# ─── Transport Objects ───

@dataclass
class RawContent:
    """Raw bytes fetched by a connector."""
    data: bytes
    source_uri: str
    filename: str
    mime_type: str | None = None
    extension: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0

    def __post_init__(self) -> None:
        self.size_bytes = len(self.data)
        if not self.extension and "." in self.filename:
            self.extension = self.filename.rsplit(".", 1)[-1].lower()


@dataclass
class SourceObject:
    """Normalized transport object — intermediate between raw and canonical."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connector_id: str = ""
    external_id: str = ""
    object_kind: ObjectKind = ObjectKind.BLOB
    mime_type: str | None = None
    checksum: str | None = None
    version_ref: str | None = None
    parent_ref: str | None = None
    source_url: str | None = None
    timestamps: dict[str, str | None] = field(default_factory=lambda: {
        "created_at": None, "updated_at": None, "discovered_at": None,
    })
    acl_snapshot_ref: str | None = None
    raw_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_raw(raw: RawContent, connector_id: str) -> SourceObject:
        checksum = hashlib.sha256(raw.data).hexdigest()
        return SourceObject(
            connector_id=connector_id,
            external_id=raw.source_uri,
            object_kind=ObjectKind.BLOB,
            mime_type=raw.mime_type,
            checksum=checksum,
            source_url=raw.source_uri,
            timestamps={"discovered_at": str(time.time()), "created_at": None, "updated_at": None},
            metadata={**raw.metadata, "filename": raw.filename, "size_bytes": raw.size_bytes},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "external_id": self.external_id,
            "object_kind": self.object_kind.value,
            "mime_type": self.mime_type,
            "checksum": self.checksum,
            "source_url": self.source_url,
        }


@dataclass
class ExtractedContent:
    """Output of an extractor — structured text with metadata and confidence."""
    text: str
    structure: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    page: int | None = None
    language: str | None = None


@dataclass
class CanonicalDocument:
    """Retrieval-optimized document with semantic type, provenance, and ACL."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_object_ref: str = ""
    semantic_type: SemanticType = SemanticType.DOCUMENT
    title: str | None = None
    language: str | None = None
    body: str = ""
    structure: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    acl: ACL = field(default_factory=ACL)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_object_ref": self.source_object_ref,
            "semantic_type": self.semantic_type.value,
            "title": self.title,
            "language": self.language,
            "body_length": len(self.body),
            "body_preview": self.body[:200] + "..." if len(self.body) > 200 else self.body,
            "provenance": self.provenance,
            "acl": self.acl.to_dict(),
            "metadata": self.metadata,
        }


@dataclass
class Chunk:
    """Index-ready chunk with ordering, section hierarchy, and ACL reference."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    text: str = ""
    order: int = 0
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    acl_filter_ref: str | None = None
    embedding_ref: str | None = None
    chunk_type: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "order": self.order,
            "text_length": len(self.text),
            "text_preview": self.text[:150] + "..." if len(self.text) > 150 else self.text,
            "section_path": self.section_path,
            "chunk_type": self.chunk_type,
            "acl_filter_ref": self.acl_filter_ref,
        }


# ─── Indexer Health ───

@dataclass
class IndexerHealth:
    """Health signal from an index writer."""
    indexer_id: str = ""
    queue_depth: int = 0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    status: IndexerStatus = IndexerStatus.HEALTHY
    recorded_at: float = field(default_factory=time.time)


# ─── Sync Job ───

@dataclass
class SyncJob:
    """Tracks an intake job through the 12-state machine."""
    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    connector_id: str = ""
    trigger: TriggerType = TriggerType.MANUAL
    state: JobState = JobState.REGISTERED
    attempt: int = 0
    cursor_key: str | None = None
    source_object_ids: list[str] = field(default_factory=list)
    source: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    pipeline: str | None = None
    error_message: str | None = None
    errors: list[str] = field(default_factory=list)
    deferred_until: float | None = None
    # Counters
    files_found: int = 0
    files_loaded: int = 0
    documents_created: int = 0
    chunks_created: int = 0
    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def transition(self, new_state: JobState) -> None:
        self.state = new_state
        self.updated_at = time.time()
        if new_state in (JobState.ACTIVE, JobState.FAILED, JobState.DEAD_LETTERED,
                         JobState.TOMBSTONED, JobState.REVOKED):
            self.completed_at = time.time()

    def fail(self, message: str) -> None:
        self.errors.append(message)
        self.error_message = message
        self.transition(JobState.FAILED)

    def defer(self, reason: str) -> None:
        self.attempt += 1
        if self.attempt > 5:
            self.transition(JobState.DEAD_LETTERED)
            return
        delay = min(300, 2 ** self.attempt)
        self.deferred_until = time.time() + delay
        self.errors.append(f"deferred (attempt {self.attempt}): {reason}")
        self.transition(JobState.DEFERRED)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "trigger": self.trigger.value,
            "state": self.state.value,
            "attempt": self.attempt,
            "source": self.source,
            "pipeline": self.pipeline,
            "files_found": self.files_found,
            "files_loaded": self.files_loaded,
            "documents_created": self.documents_created,
            "chunks_created": self.chunks_created,
            "errors": self.errors,
            "deferred_until": self.deferred_until,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ─── Lineage Event ───

@dataclass
class LineageEvent:
    """Audit trail entry — tracks every state transition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    source_object_id: str | None = None
    document_id: str | None = None
    event_type: str = ""
    from_state: str | None = None
    to_state: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# ─── Tombstone ───

@dataclass
class Tombstone:
    """Soft-delete record for removed sources."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_object_ref: str = ""
    connector_id: str = ""
    reason: str = "deleted"
    deleted_at: float = field(default_factory=time.time)


# ─── Dead Letter ───

@dataclass
class DeadLetter:
    """Permanently failed job for investigation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    connector_id: str = ""
    error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
