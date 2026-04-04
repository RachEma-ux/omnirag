"""Base runtime interface.

Each runtime wraps a RAG framework (LangChain, LlamaIndex, Haystack)
and normalizes its outputs to the canonical data model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from omnirag.core.models import GenerationResult


class BaseRuntime(ABC):
    """Abstract base class for framework runtimes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Runtime identifier (e.g., 'langchain', 'llamaindex', 'haystack')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the runtime's dependencies are installed."""

    @abstractmethod
    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        """Load a native component (retriever, LLM chain, etc.)."""

    @abstractmethod
    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        """Execute a sequence of native components, returning canonical output."""

    def normalize_output(self, raw_output: Any) -> GenerationResult:
        """Convert a raw framework output to GenerationResult.

        Subclasses should override for framework-specific normalization.
        """
        if isinstance(raw_output, GenerationResult):
            return raw_output
        return GenerationResult(
            answer=str(raw_output),
            confidence=0.5,
            metadata={"runtime": self.name, "raw_type": type(raw_output).__name__},
        )
