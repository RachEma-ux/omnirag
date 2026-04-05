"""Admission controller — gates job submission based on limits and health."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from omnirag.intake.backpressure.registry import get_backpressure_registry
from omnirag.intake.backpressure.token_bucket import TokenBucket
from omnirag.intake.models import ConnectorConfig, SyncJob


class Decision(str, Enum):
    ACCEPT = "accept"
    DEFER = "defer"
    REJECT = "reject"


@dataclass
class AdmissionDecision:
    decision: Decision
    reason: str = ""


class AdmissionController:
    """Checks global limits, per-connector concurrency, and indexer health.

    Runs before starting any new job or transitioning to EXTRACTED.
    """

    def __init__(self, max_global_active: int = 500) -> None:
        self.max_global_active = max_global_active
        self._active_jobs: dict[str, int] = {}  # connector_id → count
        self._token_buckets: dict[str, TokenBucket] = {}

    def _get_bucket(self, connector: ConnectorConfig) -> TokenBucket:
        if connector.id not in self._token_buckets:
            self._token_buckets[connector.id] = TokenBucket.from_docs_per_minute(
                connector.rate_limits.docs_per_minute
            )
        return self._token_buckets[connector.id]

    def job_started(self, connector_id: str) -> None:
        self._active_jobs[connector_id] = self._active_jobs.get(connector_id, 0) + 1

    def job_finished(self, connector_id: str) -> None:
        count = self._active_jobs.get(connector_id, 0)
        if count > 0:
            self._active_jobs[connector_id] = count - 1

    def active_total(self) -> int:
        return sum(self._active_jobs.values())

    def active_for(self, connector_id: str) -> int:
        return self._active_jobs.get(connector_id, 0)

    def can_submit(self, connector: ConnectorConfig, job: SyncJob) -> AdmissionDecision:
        """Check if a job can proceed."""
        # 1. Global active jobs limit
        if self.active_total() >= self.max_global_active:
            return AdmissionDecision(Decision.DEFER, "global_active_limit")

        # 2. Per-connector concurrent fetchers
        active = self.active_for(connector.id)
        if active >= connector.rate_limits.concurrent_fetchers:
            return AdmissionDecision(Decision.DEFER, "connector_concurrency_limit")

        # 3. Indexer health
        registry = get_backpressure_registry()
        blocked = registry.get_blocked_indexers()
        if blocked:
            return AdmissionDecision(Decision.DEFER, f"indexer_backpressure: {blocked}")

        # 4. Token bucket rate limit
        bucket = self._get_bucket(connector)
        if not bucket.consume(1):
            return AdmissionDecision(Decision.DEFER, "rate_limit_docs_per_minute")

        return AdmissionDecision(Decision.ACCEPT)

    def to_dict(self) -> dict:
        return {
            "max_global_active": self.max_global_active,
            "active_total": self.active_total(),
            "active_per_connector": dict(self._active_jobs),
            "token_buckets": {
                k: {"available": v.available(), "capacity": v.capacity}
                for k, v in self._token_buckets.items()
            },
        }


_controller = AdmissionController()


def get_admission_controller() -> AdmissionController:
    return _controller
