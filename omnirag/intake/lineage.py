"""Lineage & audit store — full traceability from chunk to source."""

from __future__ import annotations

import time

from omnirag.intake.models import LineageEvent, Tombstone


class LineageStore:
    """Stores lineage events and tombstones for audit trail."""

    def __init__(self) -> None:
        self._events: list[LineageEvent] = []
        self._tombstones: dict[str, Tombstone] = {}

    def record(self, event: LineageEvent) -> None:
        self._events.append(event)

    def record_transition(self, job_id: str, from_state: str, to_state: str,
                          source_object_id: str | None = None,
                          document_id: str | None = None,
                          details: dict | None = None) -> None:
        self._events.append(LineageEvent(
            job_id=job_id,
            source_object_id=source_object_id,
            document_id=document_id,
            event_type="state_transition",
            from_state=from_state,
            to_state=to_state,
            details=details or {},
        ))

    def record_tombstone(self, source_object_ref: str, connector_id: str, reason: str = "deleted") -> Tombstone:
        ts = Tombstone(
            source_object_ref=source_object_ref,
            connector_id=connector_id,
            reason=reason,
        )
        self._tombstones[ts.id] = ts
        return ts

    def get_events(self, job_id: str | None = None, limit: int = 100) -> list[dict]:
        filtered = self._events
        if job_id:
            filtered = [e for e in filtered if e.job_id == job_id]
        return [
            {
                "id": e.id,
                "job_id": e.job_id,
                "event_type": e.event_type,
                "from_state": e.from_state,
                "to_state": e.to_state,
                "source_object_id": e.source_object_id,
                "document_id": e.document_id,
                "created_at": e.created_at,
            }
            for e in sorted(filtered, key=lambda x: x.created_at, reverse=True)[:limit]
        ]

    def get_tombstones(self, connector_id: str | None = None) -> list[dict]:
        filtered = self._tombstones.values()
        if connector_id:
            filtered = [t for t in filtered if t.connector_id == connector_id]
        return [
            {"id": t.id, "source_object_ref": t.source_object_ref, "reason": t.reason, "deleted_at": t.deleted_at}
            for t in filtered
        ]

    def count(self) -> dict:
        return {"events": len(self._events), "tombstones": len(self._tombstones)}


_store = LineageStore()


def get_lineage_store() -> LineageStore:
    return _store
