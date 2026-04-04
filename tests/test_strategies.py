"""Tests for execution strategies."""

from unittest.mock import MagicMock

from omnirag.core.models import GenerationResult
from omnirag.pipelines.schema import PipelineConfig, StageConfig
from omnirag.strategies.single import SingleStrategy
from omnirag.strategies.fallback import FallbackStrategy
from omnirag.strategies.ensemble import EnsembleStrategy
from omnirag.strategies.vote import VoteStrategy
from omnirag.strategies.base import confidence_threshold


def _mock_pipeline(name: str) -> PipelineConfig:
    return PipelineConfig(name=name, stages=[StageConfig(id="s1", adapter="x")])


def _mock_executor(result: GenerationResult) -> MagicMock:
    executor = MagicMock()
    executor.execute.return_value = result
    return executor


def _result(answer: str, confidence: float) -> GenerationResult:
    return GenerationResult(answer=answer, confidence=confidence)


def test_single_strategy():
    strategy = SingleStrategy()
    pipeline = _mock_pipeline("test")
    executor = _mock_executor(_result("hello", 0.9))
    result = strategy.run([pipeline], "query", executor)
    assert result.answer == "hello"
    assert result.confidence == 0.9


def test_single_strategy_empty():
    strategy = SingleStrategy()
    result = strategy.run([], "query", MagicMock())
    assert result.confidence == 0.0


def test_fallback_accepts_high_confidence():
    strategy = FallbackStrategy(condition=confidence_threshold(0.7))
    p1 = _mock_pipeline("p1")
    executor = _mock_executor(_result("good", 0.9))
    result = strategy.run([p1], "query", executor)
    assert result.answer == "good"


def test_fallback_falls_through():
    strategy = FallbackStrategy(condition=confidence_threshold(0.8))
    p1 = _mock_pipeline("p1")
    p2 = _mock_pipeline("p2")

    executor = MagicMock()
    executor.execute.side_effect = [
        _result("bad", 0.3),
        _result("better", 0.9),
    ]
    result = strategy.run([p1, p2], "query", executor)
    assert result.answer == "better"


def test_ensemble_merges():
    strategy = EnsembleStrategy()
    p1 = _mock_pipeline("p1")
    p2 = _mock_pipeline("p2")

    executor = MagicMock()
    executor.execute.side_effect = [
        _result("answer A", 0.7),
        _result("answer B", 0.9),
    ]
    result = strategy.run([p1, p2], "query", executor)
    assert result.answer == "answer B"  # highest confidence
    assert result.metadata["strategy"] == "ensemble"


def test_vote_majority():
    strategy = VoteStrategy()
    p1 = _mock_pipeline("p1")
    p2 = _mock_pipeline("p2")
    p3 = _mock_pipeline("p3")

    executor = MagicMock()
    executor.execute.side_effect = [
        _result("yes", 0.8),
        _result("yes", 0.7),
        _result("no", 0.9),
    ]
    result = strategy.run([p1, p2, p3], "query", executor)
    assert result.answer.lower() == "yes"
    assert result.metadata["winning_votes"] == 2
