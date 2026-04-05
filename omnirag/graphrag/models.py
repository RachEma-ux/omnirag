"""GraphRAG data models — entities, relationships, communities, reports."""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class QueryMode(str, Enum):
    BASIC = "basic"
    LOCAL = "local"
    GLOBAL = "global"
    DRIFT = "drift"


@dataclass
class GraphEntity:
    resolved_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = ""
    aliases: list[str] = field(default_factory=list)
    entity_type: str = ""
    acl_principals: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "resolved_id": self.resolved_id,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "entity_type": self.entity_type,
            "acl_principals": self.acl_principals,
            "metadata": self.metadata,
        }


@dataclass
class GraphRelationship:
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "RELATES_TO"
    weight: float = 1.0
    acl_principals: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
        }


@dataclass
class GraphCommunity:
    community_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: int = 0
    entity_ids: list[str] = field(default_factory=list)
    acl_principals: list[str] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> dict:
        return {
            "community_id": self.community_id,
            "level": self.level,
            "entity_count": len(self.entity_ids),
            "stale": self.stale,
        }


@dataclass
class CommunityReport:
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    community_id: str = ""
    summary: str = ""
    acl_principals: list[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)
    expires_at: float = 0

    def __post_init__(self):
        if not self.expires_at:
            self.expires_at = self.generated_at + 7 * 86400  # 7 days

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "community_id": self.community_id,
            "summary_preview": self.summary[:200] + "..." if len(self.summary) > 200 else self.summary,
            "generated_at": self.generated_at,
        }


@dataclass
class EntityMention:
    """Raw mention extracted from a chunk."""
    surface_form: str = ""
    entity_type: str = ""
    confidence: float = 0.0
    chunk_id: str = ""
    start_char: int = 0
    end_char: int = 0


@dataclass
class GraphEvidenceBundle:
    """Extended EvidenceBundle with graph-specific fields."""
    mode: QueryMode = QueryMode.BASIC
    chunks: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    community_reports: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    coverage: float = 0.0
    latency_ms: float = 0.0
    cache_hit: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "chunks_count": len(self.chunks),
            "entities_count": len(self.entities),
            "relationships_count": len(self.relationships),
            "community_reports_count": len(self.community_reports),
            "confidence": self.confidence,
            "coverage": self.coverage,
            "latency_ms": round(self.latency_ms, 1),
            "cache_hit": self.cache_hit,
        }
