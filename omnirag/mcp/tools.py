"""MCP Tools — exposed to LLMs for tool use (Claude, GPT-4, etc.)."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Tool definitions (MCP-compatible format)
TOOLS = [
    {
        "name": "search_knowledge_graph",
        "description": "Search the OmniGraph knowledge graph for entities, relationships, and community reports. Supports Local, Global, and DRIFT search modes.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "mode": {"type": "string", "enum": ["local", "global", "drift", "auto"], "default": "auto"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_documents",
        "description": "Search ingested documents using hybrid vector + keyword retrieval with citations.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_entity_details",
        "description": "Get detailed information about a specific entity: properties, aliases, relationships, community membership.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {"type": "string"},
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "get_community_report",
        "description": "Fetch the summary report for a knowledge graph community.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
            },
            "required": ["community_id"],
        },
    },
    {
        "name": "ingest_document",
        "description": "Ingest a document from a source URI (local file, URL, S3, GitHub).",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source URI (file path, URL, s3://, github://)"},
            },
            "required": ["source"],
        },
    },
]


class MCPToolProvider:
    """Provides MCP-compatible tool interface for LLM integration."""

    def list_tools(self) -> list[dict]:
        return TOOLS

    async def call_tool(self, tool_name: str, params: dict) -> Any:
        """Execute a tool by name with given parameters."""
        if tool_name == "search_knowledge_graph":
            return await self._search_graph(params)
        elif tool_name == "search_documents":
            return await self._search_docs(params)
        elif tool_name == "get_entity_details":
            return await self._get_entity(params)
        elif tool_name == "get_community_report":
            return await self._get_report(params)
        elif tool_name == "ingest_document":
            return await self._ingest(params)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _search_graph(self, params: dict) -> dict:
        from omnirag.graphrag.query.local import local_search
        from omnirag.graphrag.query.global_search import global_search
        from omnirag.graphrag.query.drift import drift_search

        query = params.get("query", "")
        mode = params.get("mode", "auto")
        top_k = params.get("top_k", 5)

        if mode == "auto":
            from omnirag.graphrag.router.router import get_query_router
            decision = get_query_router().route(query)
            mode = decision.mode.value

        if mode == "local":
            result = await local_search(query, ["public"])
        elif mode == "global":
            result = await global_search(query, ["public"])
        elif mode == "drift":
            result = await drift_search(query, ["public"])
        else:
            result = await local_search(query, ["public"])

        return {"mode": mode, "entities": result.entities[:top_k], "chunks": len(result.chunks)}

    async def _search_docs(self, params: dict) -> dict:
        from omnirag.output.retrieval.hybrid import get_retriever
        retriever = get_retriever()
        evidence = await retriever.retrieve(params.get("query", ""), ["public"], params.get("top_k", 10))
        return {"mode": evidence.mode, "chunks": [{"id": c.chunk_id, "content": c.content[:200]} for c in evidence.chunks[:5]]}

    async def _get_entity(self, params: dict) -> dict:
        from omnirag.graphrag.store import get_graph_store
        store = get_graph_store()
        entity = await store.find_entity_by_name(params.get("entity_name", ""))
        if not entity:
            return {"error": "Entity not found"}
        return entity.to_dict()

    async def _get_report(self, params: dict) -> dict:
        from omnirag.graphrag.store import get_graph_store
        store = get_graph_store()
        reports = await store.get_community_reports()
        for r in reports:
            if r.community_id == params.get("community_id"):
                return r.to_dict()
        return {"error": "Report not found"}

    async def _ingest(self, params: dict) -> dict:
        from omnirag.intake.gate import get_gate
        gate = get_gate()
        job = await gate.ingest(params.get("source", ""), {})
        return job.to_dict()


_provider = MCPToolProvider()


def get_mcp_provider() -> MCPToolProvider:
    return _provider
