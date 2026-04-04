"""OpenTelemetry tracing integration.

Creates spans for pipeline execution, stage execution, and compilation.
Falls back gracefully if OpenTelemetry SDK is not installed.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator


class TracingManager:
    """Manages OpenTelemetry tracing for OmniRAG."""

    def __init__(self, service_name: str = "omnirag") -> None:
        self.service_name = service_name
        self._tracer: Any = None
        self._enabled = False
        self._init_tracer()

    def _init_tracer(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider

            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self.service_name)
            self._enabled = True
        except ImportError:
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Any, None, None]:
        """Create a tracing span. No-op if OTel is not available."""
        if not self._enabled or self._tracer is None:
            yield None
            return

        with self._tracer.start_as_current_span(name) as s:
            if attributes:
                for k, v in attributes.items():
                    s.set_attribute(k, str(v))
            yield s

    def pipeline_span(
        self, pipeline_name: str, strategy: str
    ) -> Any:
        """Create a span for pipeline execution."""
        return self.span(
            f"pipeline.execute.{pipeline_name}",
            {"pipeline.name": pipeline_name, "pipeline.strategy": strategy},
        )

    def stage_span(
        self, pipeline_name: str, stage_id: str, mode: str
    ) -> Any:
        """Create a span for stage execution."""
        return self.span(
            f"stage.execute.{stage_id}",
            {
                "pipeline.name": pipeline_name,
                "stage.id": stage_id,
                "stage.mode": mode,
            },
        )
