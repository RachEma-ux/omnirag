"""3-stage query router: 25 YAML rules → BERT classifier → enhanced dynamic override."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml

from omnirag.graphrag.models import QueryMode, GraphEvidenceBundle

logger = structlog.get_logger(__name__)

# Thresholds
BERT_CONFIDENCE_THRESHOLD = 0.7
BASIC_TO_LOCAL_CONFIDENCE = 0.62
LOCAL_TO_DRIFT_COVERAGE = 0.45


@dataclass
class RouteDecision:
    mode: QueryMode
    confidence: float
    stage: str  # "rule_based", "classifier", "dynamic_override"
    rule_name: str | None = None
    original_mode: QueryMode | None = None


# ─── Stage 1: YAML rule-based patterns (25 rules) ───

_compiled_rules: dict[str, list[tuple[str, re.Pattern, float]]] | None = None


def _load_rules() -> dict[str, list[tuple[str, re.Pattern, float]]]:
    global _compiled_rules
    if _compiled_rules is not None:
        return _compiled_rules

    rules_path = Path(__file__).parent / "rules.yaml"
    if not rules_path.exists():
        logger.warning("router.no_rules_yaml")
        _compiled_rules = {}
        return _compiled_rules

    with open(rules_path) as f:
        raw = yaml.safe_load(f)

    _compiled_rules = {}
    mode_map = {
        "global_patterns": "global",
        "local_patterns": "local",
        "drift_patterns": "drift",
        "basic_patterns": "basic",
        "hybrid_patterns": "hybrid",
    }
    for section, mode in mode_map.items():
        entries = raw.get(section, [])
        compiled = []
        for entry in entries:
            try:
                pattern = re.compile(entry["pattern"], re.IGNORECASE)
                compiled.append((entry.get("name", ""), pattern, entry.get("confidence", 0.8)))
            except re.error as e:
                logger.warning("router.bad_pattern", name=entry.get("name"), error=str(e))
        _compiled_rules[mode] = compiled

    total = sum(len(v) for v in _compiled_rules.values())
    logger.info("router.rules_loaded", count=total)
    return _compiled_rules


def rule_based_route(query: str) -> tuple[QueryMode | None, str | None, float]:
    """Stage 1: match against 25 compiled regex patterns. Returns (mode, rule_name, confidence)."""
    rules = _load_rules()
    mode_enum = {
        "global": QueryMode.GLOBAL, "local": QueryMode.LOCAL,
        "drift": QueryMode.DRIFT, "basic": QueryMode.BASIC,
        "hybrid": QueryMode.HYBRID,
    }
    best_mode = None
    best_conf = 0.0
    best_name = None

    for mode_str, entries in rules.items():
        for name, pattern, conf in entries:
            if pattern.search(query):
                if conf > best_conf:
                    best_conf = conf
                    best_mode = mode_enum.get(mode_str)
                    best_name = name

    return best_mode, best_name, best_conf


# ─── Stage 2: BERT classifier ───

def bert_route(query: str) -> tuple[QueryMode, float]:
    """Stage 2: BERT classifier (stub → heuristic fallback)."""
    # Try loaded classifier first
    try:
        from omnirag.graphrag.router.classifier import get_classifier
        classifier = get_classifier()
        if classifier.mode != "unavailable":
            return classifier.predict(query)
    except Exception:
        pass

    # Heuristic fallback
    q = query.lower()
    if any(w in q for w in ("relationship", "connected", "relate", "entity", "between", "details about", "linked")):
        return QueryMode.LOCAL, 0.6
    if any(w in q for w in ("summary", "overview", "themes", "all", "corpus", "broad", "trends", "across")):
        return QueryMode.GLOBAL, 0.6
    if any(w in q for w in ("investigate", "explore", "connect the dots", "hypothesize", "trace")):
        return QueryMode.DRIFT, 0.6
    if any(w in q for w in ("compare", "contrast", "difference")):
        return QueryMode.HYBRID, 0.55
    return QueryMode.BASIC, 0.5


# ─── Stage 3: Enhanced Dynamic Override ───

def maybe_expand(mode: QueryMode, evidence: GraphEvidenceBundle,
                 context: dict | None = None) -> tuple[QueryMode, str | None]:
    """Stage 3: dynamic override based on 6 conditions."""
    ctx = context or {}

    # Condition 1: Low confidence → upgrade BASIC to LOCAL
    if mode == QueryMode.BASIC and evidence.confidence < BASIC_TO_LOCAL_CONFIDENCE:
        return QueryMode.LOCAL, f"confidence {evidence.confidence:.2f} < {BASIC_TO_LOCAL_CONFIDENCE}"

    # Condition 2: Low coverage → upgrade LOCAL to DRIFT
    if mode == QueryMode.LOCAL and evidence.coverage < LOCAL_TO_DRIFT_COVERAGE:
        return QueryMode.DRIFT, f"coverage {evidence.coverage:.2f} < {LOCAL_TO_DRIFT_COVERAGE}"

    # Condition 3: Graph coverage too low → downgrade to BASIC
    graph_coverage = ctx.get("graph_entity_density", 1.0)
    if mode in (QueryMode.LOCAL, QueryMode.DRIFT) and graph_coverage < 0.1:
        return QueryMode.BASIC, f"graph_entity_density {graph_coverage:.2f} < 0.1"

    # Condition 4: ACL filtered >50% of nodes → upgrade to HYBRID
    acl_filtered_pct = ctx.get("acl_filtered_pct", 0.0)
    if mode == QueryMode.LOCAL and acl_filtered_pct > 0.5:
        return QueryMode.HYBRID, f"acl_filtered {acl_filtered_pct:.0%} > 50%"

    # Condition 5: Token budget too small → downgrade to BASIC
    token_budget = ctx.get("token_budget", 2048)
    if mode in (QueryMode.GLOBAL, QueryMode.DRIFT) and token_budget < 512:
        return QueryMode.BASIC, f"token_budget {token_budget} < 512"

    # Condition 6: Cache hit available for different mode → redirect
    cached_mode = ctx.get("cached_mode")
    if cached_mode and cached_mode != mode.value:
        return QueryMode(cached_mode), f"cache_hit_redirect from {mode.value} to {cached_mode}"

    return mode, None


# ─── Router ───

class QueryRouter:
    """3-stage query routing pipeline with 25 rules."""

    def route(self, query: str, context: dict | None = None) -> RouteDecision:
        """Determine the best retrieval mode."""
        # Stage 1: Rules (25 patterns)
        mode, rule_name, conf = rule_based_route(query)
        if mode is not None and conf > 0.7:
            logger.info("router.rule_matched", mode=mode.value, rule=rule_name, confidence=conf)
            return RouteDecision(mode=mode, confidence=conf, stage="rule_based", rule_name=rule_name)

        # Stage 2: BERT classifier
        bert_mode, bert_conf = bert_route(query)
        if bert_conf >= BERT_CONFIDENCE_THRESHOLD:
            logger.info("router.bert_classified", mode=bert_mode.value, confidence=bert_conf)
            return RouteDecision(mode=bert_mode, confidence=bert_conf, stage="classifier")

        # If rules had a low-confidence match, prefer it over default
        if mode is not None and conf > bert_conf:
            return RouteDecision(mode=mode, confidence=conf, stage="rule_based_low", rule_name=rule_name)

        # Default: BASIC_RAG
        logger.info("router.default_basic", bert_conf=bert_conf)
        return RouteDecision(mode=QueryMode.BASIC, confidence=bert_conf, stage="classifier_low_confidence")

    def maybe_expand_route(self, decision: RouteDecision, evidence: GraphEvidenceBundle,
                           context: dict | None = None) -> RouteDecision:
        """Post-retrieval override: expand to broader mode if quality is low."""
        new_mode, reason = maybe_expand(decision.mode, evidence, context)
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
