"""Query router tests — rules, classifier, dynamic override."""

import pytest

from omnirag.graphrag.router.router import (
    QueryRouter, rule_based_route, bert_route, maybe_expand,
    BASIC_TO_LOCAL_CONFIDENCE, LOCAL_TO_DRIFT_COVERAGE,
)
from omnirag.graphrag.models import QueryMode, GraphEvidenceBundle


class TestRuleBasedRouting:
    def test_global_patterns(self):
        assert rule_based_route("Summarize all themes") == QueryMode.GLOBAL
        assert rule_based_route("What are the main risks across the corpus?") == QueryMode.GLOBAL
        assert rule_based_route("high-level summary") == QueryMode.GLOBAL

    def test_local_patterns(self):
        assert rule_based_route("How is OmniRAG related to Neo4j?") == QueryMode.LOCAL
        assert rule_based_route("Details about PostgreSQL") == QueryMode.LOCAL

    def test_drift_patterns(self):
        assert rule_based_route("Investigate how X connects to Y") == QueryMode.DRIFT
        assert rule_based_route("Connect the dots between A and B") == QueryMode.DRIFT

    def test_basic_patterns(self):
        assert rule_based_route("What is a vector database?") == QueryMode.BASIC

    def test_no_match(self):
        assert rule_based_route("random text without clear intent") is None


class TestBertRoute:
    def test_heuristic_fallback_local(self):
        mode, conf = bert_route("What is the relationship between X and Y?")
        assert mode == QueryMode.LOCAL
        assert conf > 0

    def test_heuristic_fallback_global(self):
        mode, conf = bert_route("Give me an overview of all themes")
        assert mode == QueryMode.GLOBAL

    def test_heuristic_fallback_basic(self):
        mode, conf = bert_route("What color is the sky?")
        assert mode == QueryMode.BASIC


class TestDynamicOverride:
    def test_basic_to_local_on_low_confidence(self):
        evidence = GraphEvidenceBundle(confidence=0.4, coverage=0.8)
        new_mode, reason = maybe_expand(QueryMode.BASIC, evidence)
        assert new_mode == QueryMode.LOCAL
        assert reason is not None

    def test_basic_stays_on_high_confidence(self):
        evidence = GraphEvidenceBundle(confidence=0.8, coverage=0.8)
        new_mode, _ = maybe_expand(QueryMode.BASIC, evidence)
        assert new_mode == QueryMode.BASIC

    def test_local_to_drift_on_low_coverage(self):
        evidence = GraphEvidenceBundle(confidence=0.8, coverage=0.3)
        new_mode, reason = maybe_expand(QueryMode.LOCAL, evidence)
        assert new_mode == QueryMode.DRIFT
        assert reason is not None

    def test_local_stays_on_high_coverage(self):
        evidence = GraphEvidenceBundle(confidence=0.8, coverage=0.8)
        new_mode, _ = maybe_expand(QueryMode.LOCAL, evidence)
        assert new_mode == QueryMode.LOCAL


class TestFullRouter:
    def test_route_known_pattern(self):
        router = QueryRouter()
        decision = router.route("Summarize all themes in the corpus")
        assert decision.mode == QueryMode.GLOBAL
        assert decision.stage == "rule_based"
        assert decision.confidence == 1.0

    def test_route_ambiguous(self):
        router = QueryRouter()
        decision = router.route("tell me something interesting")
        # Should fall through to classifier
        assert decision.stage in ("classifier", "classifier_low_confidence")

    def test_maybe_expand(self):
        router = QueryRouter()
        from omnirag.graphrag.router.router import RouteDecision
        decision = RouteDecision(mode=QueryMode.BASIC, confidence=0.5, stage="classifier")
        evidence = GraphEvidenceBundle(confidence=0.4, coverage=0.3)
        expanded = router.maybe_expand_route(decision, evidence)
        assert expanded.mode == QueryMode.LOCAL
        assert expanded.stage == "dynamic_override"
