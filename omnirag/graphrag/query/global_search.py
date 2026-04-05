"""Global search — map-reduce over community reports."""

from __future__ import annotations

import time

import structlog

from omnirag.graphrag.store import get_graph_store
from omnirag.graphrag.models import GraphEvidenceBundle, QueryMode
from omnirag.output.generation.engine import get_generation_engine

logger = structlog.get_logger(__name__)

MAP_PROMPT = """Given the following community report, answer the query in one short sentence.
If the report does not contain relevant information, respond with 'NO_INFO'.

Query: {query}
Report: {summary}

Answer:"""

REDUCE_PROMPT = """Synthesise the following answers into a coherent response. Be concise.

Answers:
{answers}

Synthesised answer:"""

SIMILARITY_THRESHOLD = 0.5


async def global_search(query: str, acl_principals: list[str]) -> GraphEvidenceBundle:
    """Map-reduce over community reports for corpus-wide themes."""
    start = time.monotonic()
    store = get_graph_store()
    engine = get_generation_engine()

    # Get ACL-filtered community reports
    reports = await store.get_community_reports(acl_principals=acl_principals)
    if not reports:
        return GraphEvidenceBundle(mode=QueryMode.GLOBAL, confidence=0.0,
                                  latency_ms=(time.monotonic() - start) * 1000)

    # Map phase: ask LLM about each report
    map_answers = []
    report_dicts = []
    for report in reports:
        prompt = MAP_PROMPT.format(query=query, summary=report.summary)
        try:
            result = await engine.generate(prompt, [])
            answer = result.answer.strip()
            if answer and "NO_INFO" not in answer.upper():
                map_answers.append(answer)
                report_dicts.append(report.to_dict())
        except Exception as e:
            logger.warning("global.map_error", report=report.report_id, error=str(e))

    if not map_answers:
        return GraphEvidenceBundle(
            mode=QueryMode.GLOBAL, confidence=0.0,
            community_reports=report_dicts,
            latency_ms=(time.monotonic() - start) * 1000,
        )

    # Reduce phase: synthesise answers
    answers_text = "\n".join(f"- {a}" for a in map_answers)
    reduce_prompt = REDUCE_PROMPT.format(answers=answers_text)
    try:
        result = await engine.generate(reduce_prompt, [])
        final_answer = result.answer
    except Exception:
        final_answer = "\n".join(map_answers)

    coverage = len(map_answers) / max(len(reports), 1)
    confidence = min(1.0, coverage * 1.2)

    return GraphEvidenceBundle(
        mode=QueryMode.GLOBAL,
        community_reports=report_dicts,
        chunks=[{"content": final_answer, "type": "synthesised"}],
        confidence=confidence,
        coverage=coverage,
        latency_ms=(time.monotonic() - start) * 1000,
    )
