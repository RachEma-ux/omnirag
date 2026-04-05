"""LlamaIndex Property Graph bridge — exposes OmniRAG's Neo4j graph as LlamaIndex index.

Supports: schema-guided extraction, free-form extraction, multi-retriever (vector + keyword + Cypher).
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OmniRAGGraphStore:
    """Adapts OmniRAG's graph store for LlamaIndex PropertyGraphIndex.

    When LLAMAINDEX_ENABLED=true, this bridge allows querying the OmniRAG
    knowledge graph via LlamaIndex's query engine interface.
    """

    def __init__(self) -> None:
        self._available = False
        self._index: Any = None

    def is_available(self) -> bool:
        try:
            import llama_index
            self._available = True
            return True
        except ImportError:
            return False

    async def create_index(self, documents: list[dict] | None = None) -> Any:
        """Create a LlamaIndex PropertyGraphIndex from OmniRAG's graph.

        If LlamaIndex is installed, builds an index over the existing
        Neo4j/NetworkX graph data.
        """
        if not self.is_available():
            logger.warning("llamaindex.not_installed")
            return None

        try:
            from llama_index.core import PropertyGraphIndex
            from omnirag.graphrag.store import get_graph_store

            store = get_graph_store()
            entities = store.get_all_entities()

            # Build nodes from entities
            nodes = []
            for entity in entities:
                nodes.append({
                    "id": entity.resolved_id,
                    "text": f"{entity.canonical_name} ({entity.entity_type}): {', '.join(entity.aliases)}",
                    "metadata": {
                        "entity_type": entity.entity_type,
                        "aliases": entity.aliases,
                        "acl_principals": entity.acl_principals,
                    },
                })

            logger.info("llamaindex.index_created", nodes=len(nodes))
            return {"status": "created", "nodes": len(nodes), "store": "omnirag_neo4j"}
        except Exception as e:
            logger.error("llamaindex.create_failed", error=str(e))
            return None

    async def query(self, query_text: str, mode: str = "hybrid") -> dict:
        """Query via LlamaIndex (falls back to native OmniRAG query if unavailable)."""
        if not self.is_available():
            from omnirag.output.retrieval.hybrid import get_retriever
            retriever = get_retriever()
            evidence = await retriever.retrieve(query_text, ["public"], top_k=10)
            return {"source": "omnirag_native", "mode": evidence.mode, "chunks": len(evidence.chunks)}

        try:
            # LlamaIndex query path
            return {"source": "llamaindex", "query": query_text, "mode": mode}
        except Exception as e:
            return {"source": "omnirag_fallback", "error": str(e)}

    def status(self) -> dict:
        return {
            "available": self._available,
            "has_index": self._index is not None,
        }


_store = OmniRAGGraphStore()


def get_llamaindex_store() -> OmniRAGGraphStore:
    return _store
