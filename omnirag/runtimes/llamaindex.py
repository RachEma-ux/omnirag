"""LlamaIndex runtime — wraps LlamaIndex components."""

from __future__ import annotations

from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime


class LlamaIndexRuntime(BaseRuntime):
    """Runtime adapter for LlamaIndex."""

    @property
    def name(self) -> str:
        return "llamaindex"

    def is_available(self) -> bool:
        try:
            import llama_index  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "LlamaIndex is not installed. Install with: pip install omnirag[llamaindex]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        self._require()
        raise NotImplementedError("LlamaIndex component loading not yet implemented")

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        self._require()
        raise NotImplementedError("LlamaIndex pipeline execution not yet implemented")
