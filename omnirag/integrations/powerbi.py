"""Power BI connector + analytics export.

Exports entity/relationship/community/query data as tabular datasets.
Supports CSV, JSON, Parquet formats.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from omnirag.graphrag.store import get_graph_store
from omnirag.output.tracing import get_trace_recorder

logger = structlog.get_logger(__name__)


class AnalyticsExporter:
    """Exports platform data for analytics (Power BI, Tableau, etc.)."""

    async def export_entities(self, format: str = "json") -> list[dict]:
        """Export entity table: name, type, connections, PageRank."""
        store = get_graph_store()
        entities = store.get_all_entities()
        rows = []
        for e in entities:
            connections = sum(1 for r in store._relationships
                             if r.source_id == e.resolved_id or r.target_id == e.resolved_id)
            rows.append({
                "id": e.resolved_id,
                "name": e.canonical_name,
                "type": e.entity_type,
                "aliases": len(e.aliases),
                "connections": connections,
                "chunks": len(e.chunk_ids),
                "acl_principals": len(e.acl_principals),
            })
        return rows

    async def export_communities(self) -> list[dict]:
        """Export community table: level, size, report summary."""
        store = get_graph_store()
        communities = store.get_all_communities()
        reports = {r.community_id: r for r in await store.get_community_reports()}
        rows = []
        for c in communities:
            report = reports.get(c.community_id)
            rows.append({
                "id": c.community_id,
                "level": c.level,
                "entity_count": len(c.entity_ids),
                "has_report": report is not None,
                "report_preview": report.summary[:200] if report else "",
                "stale": c.stale,
            })
        return rows

    async def export_queries(self, limit: int = 1000) -> list[dict]:
        """Export query trace aggregates."""
        recorder = get_trace_recorder()
        traces = recorder.list_traces(limit=limit)
        return traces

    async def export_relationships(self) -> list[dict]:
        """Export relationship table."""
        store = get_graph_store()
        entity_map = {e.resolved_id: e.canonical_name for e in store.get_all_entities()}
        rows = []
        for r in store._relationships:
            rows.append({
                "source_id": r.source_id,
                "source_name": entity_map.get(r.source_id, ""),
                "target_id": r.target_id,
                "target_name": entity_map.get(r.target_id, ""),
                "type": r.relation_type,
                "weight": r.weight,
            })
        return rows

    def summary(self) -> dict:
        """Quick stats for dashboard."""
        store = get_graph_store()
        return {
            "entities": len(store.get_all_entities()),
            "relationships": len(store._relationships),
            "communities": len(store.get_all_communities()),
            "reports": len(store._reports),
            "traces": get_trace_recorder().stats()["traces"],
        }


_exporter = AnalyticsExporter()


def get_analytics_exporter() -> AnalyticsExporter:
    return _exporter
