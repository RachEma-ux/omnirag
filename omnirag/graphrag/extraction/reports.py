"""Community report generation — LLM-based summarization."""

from __future__ import annotations

import time

import structlog

from omnirag.graphrag.models import CommunityReport, GraphCommunity, GraphEntity
from omnirag.output.generation.engine import get_generation_engine

logger = structlog.get_logger(__name__)

REPORT_PROMPT = """You are a summarisation engine. Given the list of entities and relationships in this community, produce a concise report (max 300 words) covering:
- The main theme or function of this community
- Key entities and their roles
- Any notable relationships or patterns
- If applicable, risks or opportunities mentioned

Entities:
{entities}

Relationships:
{relationships}

Report:"""


async def generate_community_report(
    community: GraphCommunity,
    entities: list[GraphEntity],
    relationship_summaries: list[str],
) -> CommunityReport:
    """Generate an LLM summary for a community."""
    entity_text = "\n".join(
        f"- {e.canonical_name} ({e.entity_type})" + (f" aliases: {', '.join(e.aliases)}" if e.aliases else "")
        for e in entities
    )
    rel_text = "\n".join(f"- {r}" for r in relationship_summaries) if relationship_summaries else "No explicit relationships extracted."

    prompt = REPORT_PROMPT.format(entities=entity_text, relationships=rel_text)

    engine = get_generation_engine()
    try:
        result = await engine.generate(prompt, [])
        summary = result.answer
    except Exception as e:
        logger.error("report.generation_failed", community=community.community_id, error=str(e))
        summary = f"Community with {len(entities)} entities: {', '.join(e.canonical_name for e in entities[:5])}"

    return CommunityReport(
        community_id=community.community_id,
        summary=summary,
        acl_principals=community.acl_principals,
    )
