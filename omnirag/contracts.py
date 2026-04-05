"""OmniGraph Service Contracts — 23 Python Protocols.

Every service in the platform implements one or more of these interfaces.
This ensures pluggability: swap implementations without rewriting the platform.

Ref: Engineering Spec §6, Tech Spec §4, Artifacts §2
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Protocol, runtime_checkable


# ─── 1. Ingestion Layer ───

@runtime_checkable
class Parser(Protocol):
    """SourceAsset → Document"""
    async def parse(self, asset: Any) -> Any: ...

@runtime_checkable
class Normalizer(Protocol):
    """Document → canonical Chunks"""
    async def normalize(self, document: Any) -> list: ...

@runtime_checkable
class Extractor(Protocol):
    """Document/Chunk → list[Extraction] (mode: regex/llm/schema/hybrid)"""
    async def extract(self, source_ref: str, text: str, mode: str = "hybrid",
                      schema_hint: str | None = None) -> list: ...

@runtime_checkable
class EntityResolver(Protocol):
    """list[Extraction] → resolved Entities + ResolutionCases"""
    async def resolve(self, extractions: list) -> tuple[list, list]: ...


# ─── 2. Graph Construction Layer ───

@runtime_checkable
class GraphBuilder(Protocol):
    """Entities + Relations → graph store writes"""
    async def build(self, entities: list, relations: list) -> Any: ...

@runtime_checkable
class CommunityBuilder(Protocol):
    """Graph → hierarchical Communities (Leiden)"""
    async def compute_communities(self, min_levels: int = 3) -> list: ...

@runtime_checkable
class ReportGenerator(Protocol):
    """Community → CommunityReport (LLM)"""
    async def generate_report(self, community_id: str, force_refresh: bool = False) -> Any: ...

@runtime_checkable
class Embedder(Protocol):
    """text → Embedding vector"""
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ─── 3. Persistence Layer ───

@runtime_checkable
class GraphStore(Protocol):
    """Entity/Relation CRUD + graph traversal"""
    async def upsert_entity(self, entity: Any) -> None: ...
    async def upsert_relationship(self, relation: Any) -> None: ...
    async def get_neighbors(self, entity_id: str, max_hops: int = 2,
                            acl_principals: list[str] | None = None) -> list: ...

@runtime_checkable
class VectorStore(Protocol):
    """ANN search (pgvector / Qdrant / Faiss)"""
    async def write(self, chunks: list, embeddings: list) -> int: ...
    async def search(self, query_vector: list[float], acl_principals: list[str],
                     top_k: int = 10) -> list: ...

@runtime_checkable
class TextIndex(Protocol):
    """Full-text search (PostgreSQL FTS / Elasticsearch)"""
    async def write(self, chunks: list) -> int: ...
    async def search(self, query_text: str, acl_principals: list[str],
                     top_k: int = 10) -> list: ...

@runtime_checkable
class GraphAlgorithm(Protocol):
    """PageRank, centrality, etc."""
    async def compute_pagerank(self) -> dict[str, float]: ...
    async def compute_centrality(self, algorithm: str = "betweenness") -> dict[str, float]: ...


# ─── 4. Query Layer ───

@runtime_checkable
class QueryRouter(Protocol):
    """query → QueryPlan (3-stage)"""
    def route(self, query: str, context: Any | None = None) -> Any: ...

@runtime_checkable
class RetrievalPlanner(Protocol):
    """QueryPlan → retrieval execution steps"""
    async def plan(self, query_plan: Any) -> list: ...

@runtime_checkable
class GraphRetriever(Protocol):
    """Subgraph retrieval from graph store"""
    async def retrieve(self, entity_ids: list[str], max_hops: int = 2,
                       acl_principals: list[str] | None = None) -> Any: ...

@runtime_checkable
class VectorRetriever(Protocol):
    """Chunk retrieval from vector store"""
    async def retrieve(self, query: str, acl_principals: list[str],
                       top_k: int = 10) -> list: ...

@runtime_checkable
class HybridRetriever(Protocol):
    """Fusion of multiple retrievers"""
    async def retrieve(self, query: str, acl_principals: list[str],
                       top_k: int = 10, filters: dict | None = None) -> Any: ...

@runtime_checkable
class ContextBuilder(Protocol):
    """Retrieved data → ContextBundle with token budget"""
    async def build(self, retrieval_result: Any, budget: int = 2048) -> Any: ...


# ─── 5. Authorization ───

@runtime_checkable
class AuthorizationEngine(Protocol):
    """Filter by ACL — pre/during/post retrieval"""
    def filter_nodes(self, nodes: list, user_roles: list[str]) -> list: ...
    def filter_chunks(self, chunks: list, user_roles: list[str]) -> list: ...
    def check_access(self, node_id: str, user_roles: list[str]) -> bool: ...


# ─── 6. Caching ───

@runtime_checkable
class CacheManager(Protocol):
    """Get/set/invalidate with mode-specific TTL"""
    def get(self, key: str) -> Any | None: ...
    def put(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    def invalidate(self, pattern: str) -> int: ...


# ─── 7. Reasoning + Synthesis ───

@runtime_checkable
class Reasoner(Protocol):
    """ContextBundle → Answer (LLM)"""
    async def reason(self, context: Any, query: str) -> Any: ...

@runtime_checkable
class AnswerSynthesizer(Protocol):
    """Final answer + citations + trace"""
    async def synthesize(self, answer: Any, context: Any, plan: Any) -> Any: ...

@runtime_checkable
class TraceRecorder(Protocol):
    """Persist AnswerTrace, MetricEvent"""
    async def record_trace(self, trace: Any) -> None: ...
    async def record_metric(self, event: Any) -> None: ...


# ─── 8. Workflow ───

@runtime_checkable
class WorkflowRunner(Protocol):
    """LangGraph / AutoGen execution"""
    async def run(self, workflow_type: str, inputs: dict) -> Any: ...
    async def get_status(self, run_id: str) -> Any: ...

@runtime_checkable
class ToolProvider(Protocol):
    """MCP tools exposure"""
    def list_tools(self) -> list[dict]: ...
    async def call_tool(self, tool_name: str, params: dict) -> Any: ...


# ─── Contract Registry ───

_implementations: dict[str, list[type]] = {}


def register_implementation(contract_name: str, impl_class: type) -> None:
    """Register a class as implementing a contract."""
    _implementations.setdefault(contract_name, []).append(impl_class)


def get_implementations(contract_name: str) -> list[type]:
    return _implementations.get(contract_name, [])


def list_contracts() -> list[str]:
    """List all 23 contract names."""
    return [
        "Parser", "Normalizer", "Extractor", "EntityResolver",
        "GraphBuilder", "CommunityBuilder", "ReportGenerator", "Embedder",
        "GraphStore", "VectorStore", "TextIndex", "GraphAlgorithm",
        "QueryRouter", "RetrievalPlanner", "GraphRetriever", "VectorRetriever",
        "HybridRetriever", "ContextBuilder",
        "AuthorizationEngine", "CacheManager",
        "Reasoner", "AnswerSynthesizer", "TraceRecorder",
        "WorkflowRunner", "ToolProvider",
    ]
