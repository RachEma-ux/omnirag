"""LangChain runtime — wraps LangChain components."""

from __future__ import annotations

from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime


class LangChainRuntime(BaseRuntime):
    """Runtime adapter for LangChain."""

    @property
    def name(self) -> str:
        return "langchain"

    def is_available(self) -> bool:
        try:
            import langchain  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "LangChain is not installed. Install with: pip install omnirag[langchain]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        self._require()
        # TODO: Implement component loading (VectorStore, Retriever, LLMChain, etc.)
        raise NotImplementedError("LangChain component loading not yet implemented")

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        self._require()
        # TODO: Execute LCEL chain and normalize output
        raise NotImplementedError("LangChain pipeline execution not yet implemented")
