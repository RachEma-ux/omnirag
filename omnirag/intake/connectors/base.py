"""Base connector interface — 7 methods per reference spec."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from omnirag.intake.models import ACL, RawContent, SourceObject


class BaseConnector(ABC):
    """Source adapter — normalizes any source into a common contract.

    Every connector implements 7 methods:
    1. discover() — list what exists at the source
    2. fetch()    — retrieve raw bytes or records
    3. changes()  — get deltas since a cursor/checkpoint
    4. subscribe()— register webhook/watch if supported
    5. permissions() — resolve source ACLs
    6. delete_events() — surface removals/tombstones
    7. version()  — expose revision/change/checksum info
    """

    name: str = "base"

    @abstractmethod
    async def discover(self, source: str, config: dict, cursor: str | None = None) -> list[SourceObject]:
        """List SourceObjects at the source (respect batch_size via config)."""
        ...

    @abstractmethod
    async def fetch(self, source_object: SourceObject, config: dict) -> RawContent | None:
        """Retrieve raw content for a single SourceObject."""
        ...

    async def fetch_batch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
        """Convenience: discover + fetch in one pass. Default implementation."""
        objects = await self.discover(source, config)
        for obj in objects:
            raw = await self.fetch(obj, config)
            if raw:
                yield raw

    async def changes(self, source: str, config: dict, cursor: str) -> tuple[list[SourceObject], str]:
        """Return new/modified objects since cursor, plus new cursor.
        Default: full re-discover (no incremental support)."""
        objects = await self.discover(source, config)
        new_cursor = str(len(objects))
        return objects, new_cursor

    async def subscribe(self, config: dict, callback_url: str) -> str | None:
        """Register webhook/watch. Returns subscription ID or None if unsupported."""
        return None

    async def permissions(self, source_object: SourceObject, config: dict) -> ACL:
        """Resolve current ACL for the object. Default: public."""
        return ACL(visibility="public")

    async def delete_events(self, config: dict, cursor: str) -> list[str]:
        """Return external_ids of deleted objects since cursor. Default: none."""
        return []

    async def version(self, source_object: SourceObject, config: dict) -> str | None:
        """Return current version/etag/checksum. Default: checksum from SourceObject."""
        return source_object.checksum

    @abstractmethod
    def supports(self, source: str) -> bool:
        """Return True if this connector handles the given source URI."""
        ...
