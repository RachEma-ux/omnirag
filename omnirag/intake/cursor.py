"""Cursor store — per-connector checkpoint persistence for incremental sync."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CursorEntry:
    connector_id: str
    cursor_value: str
    updated_at: float = field(default_factory=time.time)


class CursorStore:
    """In-memory cursor store (upgrade to PostgreSQL in Phase F)."""

    def __init__(self) -> None:
        self._cursors: dict[str, CursorEntry] = {}

    def get(self, connector_id: str) -> str | None:
        entry = self._cursors.get(connector_id)
        return entry.cursor_value if entry else None

    def update(self, connector_id: str, cursor_value: str) -> bool:
        """Atomic cursor update. Returns True on success."""
        self._cursors[connector_id] = CursorEntry(
            connector_id=connector_id,
            cursor_value=cursor_value,
        )
        return True

    def delete(self, connector_id: str) -> bool:
        if connector_id in self._cursors:
            del self._cursors[connector_id]
            return True
        return False

    def list(self) -> dict[str, str]:
        return {k: v.cursor_value for k, v in self._cursors.items()}


_store = CursorStore()


def get_cursor_store() -> CursorStore:
    return _store
