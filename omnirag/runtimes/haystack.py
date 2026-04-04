"""Haystack runtime — wraps Haystack components."""

from __future__ import annotations

from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime


class HaystackRuntime(BaseRuntime):
    """Runtime adapter for Haystack."""

    @property
    def name(self) -> str:
        return "haystack"

    def is_available(self) -> bool:
        try:
            import haystack  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "Haystack is not installed. Install with: pip install omnirag[haystack]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        self._require()
        raise NotImplementedError("Haystack component loading not yet implemented")

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        self._require()
        raise NotImplementedError("Haystack pipeline execution not yet implemented")
