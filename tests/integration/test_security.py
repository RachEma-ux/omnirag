"""Tests for auth + rate limiting."""

import base64
import json
import time

import pytest

from omnirag.output.auth import validate_jwt, get_default_identity, UserIdentity
from omnirag.output.rate_limiter import SlidingWindowLimiter, RateLimitConfig


class TestAuth:
    def test_default_identity(self):
        identity = get_default_identity()
        assert identity.principal == "user:dev"
        assert "rag:search" in identity.scopes
        assert "rag:admin" in identity.scopes
        assert "user:dev" in identity.user_principals
        assert "role:admin" in identity.user_principals

    def test_has_scope(self):
        identity = UserIdentity(scopes=["rag:search"])
        assert identity.has_scope("rag:search")
        assert not identity.has_scope("rag:admin")

    def test_admin_bypasses_scopes(self):
        identity = UserIdentity(scopes=["rag:admin"])
        assert identity.has_scope("rag:search")
        assert identity.has_scope("rag:export")

    def test_validate_jwt_with_valid_token(self):
        payload = {
            "sub": "user-123",
            "principal": "user:alice",
            "roles": ["auditor"],
            "scopes": ["rag:search"],
            "exp": time.time() + 3600,
        }
        # Build a fake JWT (no signature verification in dev)
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        token = f"{header}.{body}.fake-signature"

        identity = validate_jwt(token)
        assert identity is not None
        assert identity.sub == "user-123"
        assert identity.principal == "user:alice"
        assert "role:auditor" in identity.user_principals

    def test_validate_jwt_expired(self):
        payload = {"sub": "user-123", "exp": time.time() - 100}
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        token = f"{header}.{body}.sig"

        identity = validate_jwt(token)
        assert identity is None

    def test_validate_jwt_invalid(self):
        assert validate_jwt("") is None
        assert validate_jwt("not.a.jwt.at.all") is None
        assert validate_jwt("x.y") is None

    def test_user_hash(self):
        identity = UserIdentity(principal="user:alice")
        assert len(identity.user_hash) == 16


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = SlidingWindowLimiter(RateLimitConfig(search_per_minute=5))
        for _ in range(5):
            result = limiter.check("user:alice", "search")
            assert result.allowed

    def test_rejects_over_limit(self):
        limiter = SlidingWindowLimiter(RateLimitConfig(search_per_minute=2))
        limiter.check("user:alice", "search")
        limiter.check("user:alice", "search")
        result = limiter.check("user:alice", "search")
        assert not result.allowed
        assert result.retry_after is not None
        assert result.retry_after > 0

    def test_different_users_independent(self):
        limiter = SlidingWindowLimiter(RateLimitConfig(search_per_minute=1))
        assert limiter.check("user:alice", "search").allowed
        assert limiter.check("user:bob", "search").allowed
        assert not limiter.check("user:alice", "search").allowed

    def test_override_bypasses_limit(self):
        limiter = SlidingWindowLimiter(RateLimitConfig(search_per_minute=1))
        limiter.check("user:alice", "search")
        assert not limiter.check("user:alice", "search").allowed

        limiter.override("user:alice")
        assert limiter.check("user:alice", "search").allowed

        limiter.remove_override("user:alice")

    def test_headers(self):
        limiter = SlidingWindowLimiter(RateLimitConfig(search_per_minute=10))
        result = limiter.check("user:alice", "search")
        headers = limiter.headers(result)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "10"
