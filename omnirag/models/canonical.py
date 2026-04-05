"""OmniGraph Canonical Data Model — all 20+ objects from the Engineering Specification.

Extends existing intake/models.py with spec-required objects:
Extraction, ResolutionCase, QueryPlan, ContextBundle, Answer,
AnswerTrace, CacheKey, MetricEvent, AgentRun, EvaluationResult.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


# ─── Extraction (entity/relation candidate from a chunk) ───

@dataclass
class Extraction:
    """Raw extraction candidate before resolution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_ref: str = ""  # chunk_id or document_id
    type: str = ""  # "entity" | "relation" | "claim"
    candidate: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    provenance_span: dict[str, int] | None = None  # {"start": 100, "end": 150}
    extraction_mode: str = ""  # regex | llm | schema | hybrid
    model_version: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source_ref": self.source_ref, "type": self.type,
            "candidate": self.candidate, "confidence": self.confidence,
            "extraction_mode": self.extraction_mode, "provenance_span": self.provenance_span,
        }


# ─── ResolutionCase (merge decision for entity deduplication) ───

@dataclass
class ResolutionCase:
    """Records a merge/split decision during entity resolution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidate_entity_ids: list[str] = field(default_factory=list)
    merge_decision: str = ""  # "merge" | "keep_separate" | "review"
    confidence: float = 0.0
    verification_method: str = ""  # "hdbscan" | "llm" | "exact_match"
    verification_trace: str | None = None  # LLM response or clustering details
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "candidates": self.candidate_entity_ids,
            "decision": self.merge_decision, "confidence": self.confidence,
            "method": self.verification_method,
        }


# ─── QueryPlan (output of 3-stage router) ───

@dataclass
class QueryPlan:
    """Full routing trace: what mode was selected and why."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str = ""
    selected_mode: str = ""  # BASIC | LOCAL | GLOBAL | DRIFT | HYBRID
    router_stage1_rule: str | None = None
    router_stage1_confidence: float = 0.0
    router_stage2_bert_score: float | None = None
    router_stage2_mode: str | None = None
    router_stage3_override_reason: str | None = None
    router_stage3_mode: str | None = None
    final_confidence: float = 0.0
    user_roles: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "query": self.query_text[:100],
            "selected_mode": self.selected_mode,
            "stage1_rule": self.router_stage1_rule,
            "stage2_bert": self.router_stage2_bert_score,
            "stage3_override": self.router_stage3_override_reason,
            "confidence": self.final_confidence,
        }


# ─── ContextBundle (assembled context for LLM) ───

@dataclass
class ContextBundle:
    """Assembled retrieval context with token budget tracking."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    anchor_entities: list[dict] = field(default_factory=list)  # [{"id": "...", "name": "..."}]
    selected_relations: list[dict] = field(default_factory=list)  # [{"source": "...", "type": "...", "target": "..."}]
    path_summaries: list[str] = field(default_factory=list)
    supporting_chunks: list[dict] = field(default_factory=list)  # [{"text": "...", "score": 0.9}]
    community_summaries: list[dict] = field(default_factory=list)
    token_budget_total: int = 2048
    token_budget_used: int = 0
    freshness_seconds: float = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "anchor_entities": len(self.anchor_entities),
            "relations": len(self.selected_relations),
            "chunks": len(self.supporting_chunks),
            "communities": len(self.community_summaries),
            "token_budget_used": self.token_budget_used,
            "token_budget_total": self.token_budget_total,
        }


# ─── Answer (final response with citations) ───

@dataclass
class Answer:
    """Final answer with citations and evidence links."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    citations: list[dict] = field(default_factory=list)  # [{"chunk_id": "...", "text": "..."}]
    evidence_links: list[dict] = field(default_factory=list)  # [{"node_id": "...", "type": "entity"}]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text_preview": self.text[:200],
            "citation_count": len(self.citations),
            "evidence_count": len(self.evidence_links),
        }


# ─── AnswerTrace (full query audit trail) ───

@dataclass
class AnswerTrace:
    """Complete trace of a query through the pipeline."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    answer_id: str = ""
    query_plan: dict = field(default_factory=dict)
    context_bundle_id: str = ""
    llm_model: str = ""
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    cache_hit: bool = False
    acl_filtered_nodes: int = 0
    mode: str = ""
    fallback_used: bool = False
    fallback_reason: str | None = None
    user_principal_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "answer_id": self.answer_id,
            "mode": self.mode, "llm_model": self.llm_model,
            "token_usage": self.token_usage,
            "latency_ms": round(self.latency_ms, 1),
            "cache_hit": self.cache_hit,
            "acl_filtered": self.acl_filtered_nodes,
            "fallback_used": self.fallback_used,
            "query_plan": self.query_plan,
        }


# ─── CacheKey (mode-aware with ACL fingerprint) ───

@dataclass
class CacheKey:
    """Structured cache key with all versioning dimensions."""
    mode: str = ""
    query_hash: str = ""
    acl_fingerprint: str = ""
    graph_version: int = 0
    embedding_version: int = 0
    prompt_version: int = 0

    def build(self) -> str:
        return f"{self.mode}:{self.query_hash}:{self.acl_fingerprint}:{self.graph_version}:{self.embedding_version}:{self.prompt_version}"

    @staticmethod
    def hash_query(query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    @staticmethod
    def hash_acl(principals: list[str]) -> str:
        return hashlib.sha256(":".join(sorted(principals)).encode()).hexdigest()[:16]


# ─── MetricEvent (for Prometheus + PostgreSQL replay) ───

@dataclass
class MetricEvent:
    """Single metric data point for observability."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "labels": self.labels, "timestamp": self.timestamp}


# ─── AgentRun (LangGraph / AutoGen workflow execution) ───

@dataclass
class AgentRun:
    """Tracks a workflow or multi-agent execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_type: str = ""  # "full_ingestion" | "query_pipeline" | "evaluation" | "research"
    steps: list[dict] = field(default_factory=list)  # [{"step": "extract", "status": "completed", "duration_ms": 123}]
    status: str = "pending"  # pending | running | completed | failed
    final_output: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "workflow_type": self.workflow_type,
            "status": self.status, "steps": len(self.steps),
            "created_at": self.created_at, "completed_at": self.completed_at,
        }


# ─── EvaluationResult (LLM judge scoring) ───

@dataclass
class EvaluationResult:
    """LLM judge evaluation of an answer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_trace_id: str = ""
    score: float = 0.0  # 0-5
    evaluator_model: str = ""
    feedback: str = ""
    dimensions: dict[str, float] = field(default_factory=dict)  # {"relevance": 4.0, "completeness": 3.5, "accuracy": 4.5}
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "score": self.score,
            "evaluator": self.evaluator_model,
            "dimensions": self.dimensions,
        }
