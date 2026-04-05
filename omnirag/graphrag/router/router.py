"""3-stage query router: rule patterns → BERT classifier → dynamic override."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

from omnirag.graphrag.models import QueryMode, GraphEvidenceBundle

logger = structlog.get_logger(__name__)

# ─── Stage 1: Rule-based patterns ───

GLOBAL_PATTERNS = [
    re.compile(r"(what are the|summarize|list all)\s+(themes|topics|risks|trends)", re.I),
    re.compile(r"overview of\s+(entire|whole|all)\s+(corpus|dataset|documents)", re.I),
    re.compile(r"high.?level\s+summary", re.I),
    re.compile(r"(across all|corpus.?wide|overall|broad)\s+", re.I),
]

LOCAL_PATTERNS = [
    re.compile(r"how\s+(is|are)\s+(\w+)\s+related\s+to\s+(\w+)", re.I),
    re.compile(r"what\s+does\s+(\w+)\s+say\s+about\s+(\w+)", re.I),
    re.compile(r"details?\s+(of|about|on)\s+", re.I),
    re.compile(r"(entity|person|company|org)\s+", re.I),
]

DRIFT_PATTERNS = [
    re.compile(r"investigate\s+(how|why|whether)", re.I),
    re.compile(r"connect\s+the\s+dots", re.I),
    re.compile(r"explore\s+the\s+relationship", re.I),
    re.compile(r"hypothesize", re.I),
    re.compile(r"trace\s+(the|how)", re.I),
]

BASIC_PATTERNS = [
    re.compile(r"what\s+(is|are)\s+(a|the)\s+(fact|definition|value)", re.I),
    re.compile(r"when\s+did\s+\w+\s+happen", re.I),
    re.compile(r"^(who|what|where|when)\s+\w+\s*\?$", re.I),
]

# Thresholds
BERT_CONFIDENCE_THRESHOLD = 0.7
BASIC_TO_LOCAL_CONFIDENCE = 0.62
LOCAL_TO_DRIFT_COVERAGE = 0.45


@dataclass
class RouteDecision:
    mode: QueryMode
    confidence: float
    stage: str  # "rule_based", "classifier", "dynamic_override"
    original_mode: QueryMode | None = None


def rule_based_route(query: str) -> QueryMode | None:
    """Stage 1: match against compiled regex patterns."""
    for pattern in GLOBAL_PATTERNS:
        if pattern.search(query):
            return QueryMode.GLOBAL
    for pattern in LOCAL_PATTERNS:
        if pattern.search(query):
            return QueryMode.LOCAL
    for pattern in DRIFT_PATTERNS:
        if pattern.search(query):
            return QueryMode.DRIFT
    for pattern in BASIC_PATTERNS:
        if pattern.search(query):
            return QueryMode.BASIC
    return None


def bert_route(query: str) -> tuple[QueryMode, float]:
    """Stage 2: BERT classifier (stub — returns BASIC with low confidence when model unavailable)."""
    try:
        import httpx
        resp = httpx.post("http://bert-classifier/predict", json={"text": query}, timeout=5)
        if resp.status_code == 200:
            probs = resp.json()["probabilities"]
            modes = [QueryMode.BASIC, QueryMode.LOCAL, QueryMode.GLOBAL, QueryMode.DRIFT]
            idx = max(range(4), key=lambda i: probs[i])
            return modes[idx], probs[idx]
    except Exception:
        pass

    # Fallback heuristic when BERT unavailable
    query_lower = query.lower()
    if any(w in query_lower for w in ("relationship", "connected", "relate", "entity", "between")):
        return QueryMode.LOCAL, 0.6
    if any(w in query_lower for w in ("summary", "overview", "themes", "all", "corpus")):
        return QueryMode.GLOBAL, 0.6
    return QueryMode.BASIC, 0.5


def maybe_expand(mode: QueryMode, evidence: GraphEvidenceBundle) -> tuple[QueryMode, str | None]:
    """Stage 3: dynamic override based on confidence and coverage."""
    if mode == QueryMode.BASIC and evidence.confidence < BASIC_TO_LOCAL_CONFIDENCE:
        return QueryMode.LOCAL, f"confidence {evidence.confidence:.2f} < {BASIC_TO_LOCAL_CONFIDENCE}"
    if mode == QueryMode.LOCAL and evidence.coverage < LOCAL_TO_DRIFT_COVERAGE:
        return QueryMode.DRIFT, f"coverage {evidence.coverage:.2f} < {LOCAL_TO_DRIFT_COVERAGE}"
    return mode, None


class QueryRouter:
    """3-stage query routing pipeline."""

    def route(self, query: str) -> RouteDecision:
        """Determine the best retrieval mode for a query."""
        # Stage 1: Rules
        mode = rule_based_route(query)
        if mode is not None:
            logger.info("router.rule_matched", mode=mode.value, query=query[:50])
            return RouteDecision(mode=mode, confidence=1.0, stage="rule_based")

        # Stage 2: BERT classifier
        mode, confidence = bert_route(query)
        if confidence >= BERT_CONFIDENCE_THRESHOLD:
            logger.info("router.bert_classified", mode=mode.value, confidence=confidence)
            return RouteDecision(mode=mode, confidence=confidence, stage="classifier")

        # Default: BASIC_RAG (safe fallback)
        logger.info("router.default_basic", confidence=confidence)
        return RouteDecision(mode=QueryMode.BASIC, confidence=confidence, stage="classifier_low_confidence")

    def maybe_expand_route(self, decision: RouteDecision, evidence: GraphEvidenceBundle) -> RouteDecision:
        """Post-retrieval override: expand to broader mode if quality is low."""
        new_mode, reason = maybe_expand(decision.mode, evidence)
        if new_mode != decision.mode:
            logger.info("router.dynamic_override", from_mode=decision.mode.value,
                        to_mode=new_mode.value, reason=reason)
            return RouteDecision(
                mode=new_mode, confidence=evidence.confidence,
                stage="dynamic_override", original_mode=decision.mode,
            )
        return decision


_router = QueryRouter()


def get_query_router() -> QueryRouter:
    return _router
