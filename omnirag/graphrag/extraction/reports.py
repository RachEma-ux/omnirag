"""Community report generation — 3-tier fallback: LLM → local model → template.

Tier 1: Full LLM (configured adapter) — quality 1.0
Tier 2: Local small model (Ollama TinyLlama) — quality 0.7
Tier 3: Template-based (no LLM) — quality 0.4
"""

from __future__ import annotations

import asyncio
import time

import structlog

from omnirag.graphrag.models import CommunityReport, GraphCommunity, GraphEntity, GraphRelationship
from omnirag.graphrag.extraction.report_templates import generate_template_report
from omnirag.output.generation.engine import get_generation_engine, OllamaAdapter

logger = structlog.get_logger(__name__)

LLM_TIMEOUT = 10.0
LOCAL_MODEL_TIMEOUT = 5.0

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
    relationships: list[GraphRelationship] | None = None,
) -> CommunityReport:
    """Generate a community report with 3-tier fallback."""

    entity_text = "\n".join(
        f"- {e.canonical_name} ({e.entity_type})" + (f" aliases: {', '.join(e.aliases)}" if e.aliases else "")
        for e in entities
    )
    rel_text = "\n".join(f"- {r}" for r in relationship_summaries) if relationship_summaries else "No explicit relationships."
    prompt = REPORT_PROMPT.format(entities=entity_text, relationships=rel_text)

    # ── Tier 1: Primary LLM ──
    engine = get_generation_engine()
    if engine.get_adapter_name() != "fallback":
        try:
            result = await asyncio.wait_for(engine.generate(prompt, []), timeout=LLM_TIMEOUT)
            if result.answer and "Generation failed" not in result.answer:
                report = CommunityReport(
                    community_id=community.community_id,
                    summary=result.answer,
                    acl_principals=community.acl_principals,
                )
                report.summary = f"[tier:1] {report.summary}"
                logger.info("report.tier1", community=community.community_id[:8])
                return report
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("report.tier1_failed", error=str(e))

    # ── Tier 2: Local small model (Ollama) ──
    try:
        local_adapter = OllamaAdapter(model="tinyllama", base_url="http://localhost:11434")
        answer, _ = await asyncio.wait_for(local_adapter.generate(prompt), timeout=LOCAL_MODEL_TIMEOUT)
        if answer and len(answer) > 20:
            report = CommunityReport(
                community_id=community.community_id,
                summary=f"[tier:2] {answer}",
                acl_principals=community.acl_principals,
            )
            logger.info("report.tier2", community=community.community_id[:8])
            return report
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("report.tier2_failed", error=str(e))

    # ── Tier 3: Template-based (no LLM) ──
    logger.info("report.tier3", community=community.community_id[:8])
    report = generate_template_report(community, entities, relationships or [])
    report.summary = f"[tier:3] {report.summary}"
    return report
