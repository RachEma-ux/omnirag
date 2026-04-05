"""Analytics API — export data for Power BI, dashboards, reporting."""

from __future__ import annotations

from fastapi import APIRouter

from omnirag.integrations.powerbi import get_analytics_exporter
from omnirag.mcp.tools import get_mcp_provider
from omnirag.workflows.langgraph_runner import get_workflow_runner
from omnirag.integrations.llamaindex import get_llamaindex_store

router = APIRouter(prefix="/v1")


@router.get("/analytics/entities", tags=["analytics"])
async def export_entities():
    return await get_analytics_exporter().export_entities()


@router.get("/analytics/communities", tags=["analytics"])
async def export_communities():
    return await get_analytics_exporter().export_communities()


@router.get("/analytics/relationships", tags=["analytics"])
async def export_relationships():
    return await get_analytics_exporter().export_relationships()


@router.get("/analytics/queries", tags=["analytics"])
async def export_queries(limit: int = 1000):
    return await get_analytics_exporter().export_queries(limit)


@router.get("/analytics/summary", tags=["analytics"])
async def analytics_summary():
    return get_analytics_exporter().summary()


# ─── MCP Tools ───

@router.get("/mcp/tools", tags=["mcp"])
async def list_mcp_tools():
    return get_mcp_provider().list_tools()


@router.post("/mcp/call", tags=["mcp"])
async def call_mcp_tool(tool_name: str, params: dict = {}):
    return await get_mcp_provider().call_tool(tool_name, params)


# ─── Workflows ───

@router.post("/workflows/run", tags=["workflows"])
async def run_workflow(workflow_type: str, inputs: dict = {}):
    return (await get_workflow_runner().run(workflow_type, inputs)).to_dict()


@router.get("/workflows/{run_id}", tags=["workflows"])
async def workflow_status(run_id: str):
    run = get_workflow_runner().get_status(run_id)
    if not run:
        return {"error": "Run not found"}
    return run.to_dict()


@router.get("/workflows", tags=["workflows"])
async def list_workflows():
    return {"available": get_workflow_runner().list_workflows(), "runs": get_workflow_runner().list_runs()}


# ─── LlamaIndex ───

@router.get("/integrations/llamaindex/status", tags=["integrations"])
async def llamaindex_status():
    return get_llamaindex_store().status()


@router.post("/integrations/llamaindex/query", tags=["integrations"])
async def llamaindex_query(query: str, mode: str = "hybrid"):
    return await get_llamaindex_store().query(query, mode)
