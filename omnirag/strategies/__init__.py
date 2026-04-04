"""Execution strategies for multi-pipeline orchestration."""

from omnirag.strategies.base import ExecutionStrategy
from omnirag.strategies.ensemble import EnsembleStrategy
from omnirag.strategies.fallback import FallbackStrategy
from omnirag.strategies.single import SingleStrategy
from omnirag.strategies.vote import VoteStrategy

__all__ = [
    "ExecutionStrategy",
    "SingleStrategy",
    "FallbackStrategy",
    "EnsembleStrategy",
    "VoteStrategy",
]
