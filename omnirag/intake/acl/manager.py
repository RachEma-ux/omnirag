"""ACL snapshot manager — capture, store, propagate, revoke."""

from __future__ import annotations

import time
import uuid

from omnirag.intake.models import ACL, CanonicalDocument, Chunk, LineageEvent, Tombstone


class ACLSnapshot:
    """Immutable ACL snapshot."""
    def __init__(self, acl: ACL) -> None:
        self.id = str(uuid.uuid4())
        self.acl = acl
        self.created_at = time.time()


class ACLManager:
    """Manages ACL snapshots, propagation, and revocation."""

    def __init__(self) -> None:
        self._snapshots: dict[str, ACLSnapshot] = {}

    def capture(self, acl: ACL) -> ACLSnapshot:
        """Create an immutable snapshot."""
        snap = ACLSnapshot(acl)
        self._snapshots[snap.id] = snap
        return snap

    def get(self, snapshot_id: str) -> ACLSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def bind_document(self, doc: CanonicalDocument, snapshot: ACLSnapshot) -> None:
        """Attach ACL snapshot to a document."""
        doc.acl = snapshot.acl
        doc.metadata["acl_snapshot_ref"] = snapshot.id

    def bind_chunks(self, chunks: list[Chunk], snapshot: ACLSnapshot) -> None:
        """Attach ACL filter ref to all chunks."""
        for chunk in chunks:
            chunk.acl_filter_ref = snapshot.id

    def check_access(self, snapshot_id: str, user_principals: list[str], user_groups: list[str]) -> bool:
        """Check if user has access based on ACL snapshot."""
        snap = self.get(snapshot_id)
        if not snap:
            return False

        acl = snap.acl
        if acl.visibility.value in ("public", "tenant"):
            return True
        if any(p in acl.principals for p in user_principals):
            return True
        if any(g in acl.groups for g in user_groups):
            return True
        return False


_manager = ACLManager()


def get_acl_manager() -> ACLManager:
    return _manager
