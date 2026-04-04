"""OmniRAG custom exceptions."""


class OmniRAGError(Exception):
    """Base exception for OmniRAG."""


class PipelineValidationError(OmniRAGError):
    """Raised when a pipeline YAML is invalid."""


class PipelineCycleError(PipelineValidationError):
    """Raised when a pipeline DAG contains a cycle."""


class AdapterNotFoundError(OmniRAGError):
    """Raised when a requested adapter is not registered."""


class AdapterMaturityWarning(UserWarning):
    """Warning when using non-core adapter in compiled mode."""


class RuntimeNotAvailableError(OmniRAGError):
    """Raised when a runtime (LangChain, etc.) is not installed."""


class ExecutionError(OmniRAGError):
    """Raised when pipeline execution fails."""


class StageExecutionError(ExecutionError):
    """Raised when a single stage fails during execution."""

    def __init__(self, stage_id: str, message: str) -> None:
        self.stage_id = stage_id
        super().__init__(f"Stage '{stage_id}' failed: {message}")


class StrategyExhaustedError(ExecutionError):
    """Raised when all fallback strategies are exhausted."""
