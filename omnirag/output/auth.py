"""JWT authentication — RS256 validation, principal extraction, scope enforcement."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field


@dataclass
class UserIdentity:
    sub: str = "anonymous"
    principal: str = "public"
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)

    @property
    def user_principals(self) -> list[str]:
        """Combined list: [principal] + [role:x for x in roles]."""
        return [self.principal] + [f"role:{r}" for r in self.roles]

    @property
    def user_hash(self) -> str:
        return hashlib.sha256(self.principal.encode()).hexdigest()[:16]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "rag:admin" in self.scopes


def validate_jwt(token: str) -> UserIdentity | None:
    """Validate JWT and extract identity.

    In production: verify RS256 signature, check expiry, check audience.
    Current: decode payload without verification (dev mode).
    """
    if not token:
        return None

    try:
        import json
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (no signature verification in dev)
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Check expiry
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return None

        return UserIdentity(
            sub=payload.get("sub", "unknown"),
            principal=payload.get("principal", f"user:{payload.get('sub', 'unknown')}"),
            roles=payload.get("roles", []),
            scopes=payload.get("scopes", ["rag:search"]),
        )
    except Exception:
        return None


def get_default_identity() -> UserIdentity:
    """Default identity when auth is disabled (dev mode)."""
    return UserIdentity(
        sub="dev-user",
        principal="user:dev",
        roles=["admin"],
        scopes=["rag:search", "rag:export", "rag:admin"],
    )
