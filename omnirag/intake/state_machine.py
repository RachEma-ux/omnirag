"""12-state job lifecycle + 5 terminal states.

REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED →
MATERIALIZED → ENRICHED → ACL_BOUND → CHUNKED → INDEXED → VERIFIED → ACTIVE

Terminal: DEFERRED, FAILED, TOMBSTONED, REVOKED, QUARANTINED, DEAD_LETTERED
"""

from __future__ import annotations

from omnirag.intake.models import JobState

# Valid transitions: state → set of allowed next states
TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.REGISTERED:    {JobState.DISCOVERED, JobState.FAILED, JobState.DEFERRED, JobState.QUARANTINED},
    JobState.DISCOVERED:    {JobState.AUTHORIZED, JobState.FAILED, JobState.DEFERRED, JobState.QUARANTINED},
    JobState.AUTHORIZED:    {JobState.FETCHED, JobState.FAILED, JobState.DEFERRED, JobState.REVOKED},
    JobState.FETCHED:       {JobState.EXTRACTED, JobState.FAILED, JobState.DEFERRED, JobState.QUARANTINED},
    JobState.EXTRACTED:     {JobState.MATERIALIZED, JobState.FAILED, JobState.DEFERRED, JobState.QUARANTINED},
    JobState.MATERIALIZED:  {JobState.ENRICHED, JobState.FAILED, JobState.DEFERRED},
    JobState.ENRICHED:      {JobState.ACL_BOUND, JobState.FAILED, JobState.DEFERRED},
    JobState.ACL_BOUND:     {JobState.CHUNKED, JobState.FAILED, JobState.DEFERRED},
    JobState.CHUNKED:       {JobState.INDEXED, JobState.FAILED, JobState.DEFERRED},
    JobState.INDEXED:       {JobState.VERIFIED, JobState.FAILED, JobState.DEFERRED},
    JobState.VERIFIED:      {JobState.ACTIVE, JobState.FAILED},
    JobState.ACTIVE:        {JobState.TOMBSTONED, JobState.REVOKED},
    # Terminal states can only go to DEAD_LETTERED
    JobState.DEFERRED:      {JobState.REGISTERED, JobState.DEAD_LETTERED},
    JobState.FAILED:        {JobState.REGISTERED, JobState.DEAD_LETTERED},  # retry or give up
    JobState.QUARANTINED:   {JobState.REGISTERED, JobState.TOMBSTONED},     # review then retry or kill
}

TERMINAL_STATES = {
    JobState.ACTIVE,
    JobState.TOMBSTONED,
    JobState.REVOKED,
    JobState.DEAD_LETTERED,
}

EXCEPTION_STATES = {
    JobState.DEFERRED,
    JobState.FAILED,
    JobState.QUARANTINED,
}


def can_transition(from_state: JobState, to_state: JobState) -> bool:
    """Check if a state transition is valid."""
    allowed = TRANSITIONS.get(from_state)
    if allowed is None:
        return False
    return to_state in allowed


def validate_transition(from_state: JobState, to_state: JobState) -> None:
    """Raise if transition is invalid."""
    if not can_transition(from_state, to_state):
        raise ValueError(
            f"Invalid state transition: {from_state.value} → {to_state.value}. "
            f"Allowed: {[s.value for s in TRANSITIONS.get(from_state, set())]}"
        )


def is_terminal(state: JobState) -> bool:
    return state in TERMINAL_STATES


def is_exception(state: JobState) -> bool:
    return state in EXCEPTION_STATES


def is_active(state: JobState) -> bool:
    return state not in TERMINAL_STATES and state not in EXCEPTION_STATES
