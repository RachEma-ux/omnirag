"""Unit tests for the 12-state job state machine."""

import pytest

from omnirag.intake.models import JobState, SyncJob
from omnirag.intake.state_machine import (
    can_transition,
    validate_transition,
    is_terminal,
    is_exception,
    is_active,
    TRANSITIONS,
)


class TestStateTransitions:
    """Verify valid and invalid state transitions."""

    def test_happy_path(self):
        """Full 12-state happy path should work."""
        path = [
            JobState.REGISTERED, JobState.DISCOVERED, JobState.AUTHORIZED,
            JobState.FETCHED, JobState.EXTRACTED, JobState.MATERIALIZED,
            JobState.ENRICHED, JobState.ACL_BOUND, JobState.CHUNKED,
            JobState.INDEXED, JobState.VERIFIED, JobState.ACTIVE,
        ]
        for i in range(len(path) - 1):
            assert can_transition(path[i], path[i + 1]), f"{path[i]} → {path[i+1]} should be valid"

    def test_any_state_can_fail(self):
        """Most active states can transition to FAILED."""
        for state in [JobState.REGISTERED, JobState.DISCOVERED, JobState.AUTHORIZED,
                      JobState.FETCHED, JobState.EXTRACTED, JobState.MATERIALIZED,
                      JobState.ENRICHED, JobState.ACL_BOUND, JobState.CHUNKED,
                      JobState.INDEXED]:
            assert can_transition(state, JobState.FAILED)

    def test_any_state_can_defer(self):
        """Most active states can transition to DEFERRED."""
        for state in [JobState.REGISTERED, JobState.DISCOVERED, JobState.AUTHORIZED,
                      JobState.FETCHED, JobState.EXTRACTED, JobState.MATERIALIZED,
                      JobState.ENRICHED, JobState.ACL_BOUND, JobState.CHUNKED,
                      JobState.INDEXED]:
            assert can_transition(state, JobState.DEFERRED)

    def test_active_to_tombstoned(self):
        """ACTIVE can be tombstoned (source deleted)."""
        assert can_transition(JobState.ACTIVE, JobState.TOMBSTONED)

    def test_active_to_revoked(self):
        """ACTIVE can be revoked (permissions changed)."""
        assert can_transition(JobState.ACTIVE, JobState.REVOKED)

    def test_deferred_can_retry(self):
        """DEFERRED can go back to REGISTERED for retry."""
        assert can_transition(JobState.DEFERRED, JobState.REGISTERED)

    def test_deferred_to_dead_letter(self):
        """DEFERRED can escalate to DEAD_LETTERED."""
        assert can_transition(JobState.DEFERRED, JobState.DEAD_LETTERED)

    def test_invalid_skip(self):
        """Cannot skip states (e.g., REGISTERED → EXTRACTED)."""
        assert not can_transition(JobState.REGISTERED, JobState.EXTRACTED)

    def test_invalid_backward(self):
        """Cannot go backward (e.g., ACTIVE → FETCHED)."""
        assert not can_transition(JobState.ACTIVE, JobState.FETCHED)

    def test_validate_raises_on_invalid(self):
        """validate_transition should raise ValueError for invalid transitions."""
        with pytest.raises(ValueError, match="Invalid state transition"):
            validate_transition(JobState.REGISTERED, JobState.ACTIVE)

    def test_terminal_states(self):
        """ACTIVE, TOMBSTONED, REVOKED, DEAD_LETTERED are terminal."""
        assert is_terminal(JobState.ACTIVE)
        assert is_terminal(JobState.TOMBSTONED)
        assert is_terminal(JobState.REVOKED)
        assert is_terminal(JobState.DEAD_LETTERED)
        assert not is_terminal(JobState.REGISTERED)

    def test_exception_states(self):
        """DEFERRED, FAILED, QUARANTINED are exception states."""
        assert is_exception(JobState.DEFERRED)
        assert is_exception(JobState.FAILED)
        assert is_exception(JobState.QUARANTINED)
        assert not is_exception(JobState.ACTIVE)

    def test_active_check(self):
        """Active states are neither terminal nor exception."""
        assert is_active(JobState.REGISTERED)
        assert is_active(JobState.FETCHED)
        assert not is_active(JobState.ACTIVE)
        assert not is_active(JobState.DEFERRED)


class TestSyncJob:
    """Test SyncJob model methods."""

    def test_transition(self):
        job = SyncJob()
        assert job.state == JobState.REGISTERED
        job.transition(JobState.DISCOVERED)
        assert job.state == JobState.DISCOVERED

    def test_fail(self):
        job = SyncJob()
        job.fail("test error")
        assert job.state == JobState.FAILED
        assert "test error" in job.errors
        assert job.completed_at is not None

    def test_defer_with_backoff(self):
        job = SyncJob()
        job.defer("backpressure")
        assert job.state == JobState.DEFERRED
        assert job.attempt == 1
        assert job.deferred_until is not None
        # Backoff: 2^1 = 2 seconds
        assert job.deferred_until > job.created_at

    def test_defer_escalates_to_dead_letter(self):
        job = SyncJob()
        job.attempt = 5  # Already at max
        job.defer("still backpressured")
        assert job.state == JobState.DEAD_LETTERED

    def test_to_dict(self):
        job = SyncJob(source="file:///test.txt")
        d = job.to_dict()
        assert d["source"] == "file:///test.txt"
        assert d["state"] == "registered"
        assert isinstance(d["errors"], list)
