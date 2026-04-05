"""Tests for backpressure components — token bucket, admission, circuit breaker."""

import time

import pytest

from omnirag.intake.backpressure.token_bucket import TokenBucket
from omnirag.intake.backpressure.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
from omnirag.intake.backpressure.dead_letter import DeadLetterQueue
from omnirag.intake.models import SyncJob


class TestTokenBucket:
    def test_consume_within_capacity(self):
        bucket = TokenBucket(rate_per_second=10, capacity=5)
        assert bucket.consume(1)
        assert bucket.consume(1)

    def test_consume_exhausts_capacity(self):
        bucket = TokenBucket(rate_per_second=0, capacity=3)
        assert bucket.consume(1)
        assert bucket.consume(1)
        assert bucket.consume(1)
        assert not bucket.consume(1)

    def test_refill(self):
        bucket = TokenBucket(rate_per_second=1000, capacity=10)
        bucket.tokens = 0
        bucket.last_refill = time.monotonic() - 1
        assert bucket.consume(1)

    def test_from_docs_per_minute(self):
        bucket = TokenBucket.from_docs_per_minute(600)
        assert bucket.rate == 10.0
        assert bucket.capacity == 60


class TestCircuitBreaker:
    def test_closed_state_passes(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass
        assert cb.state == CircuitState.OPEN

    def test_open_rejects(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=60)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "ok")

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=0)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        cb.last_failure_time = time.time() - 1
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_to_dict(self):
        cb = CircuitBreaker(name="test-cb")
        d = cb.to_dict()
        assert d["name"] == "test-cb"
        assert d["state"] == "closed"


class TestDeadLetterQueue:
    def test_insert_and_list(self):
        dlq = DeadLetterQueue()
        job = SyncJob(source="file:///test.txt")
        job.error_message = "test failure"
        dlq.insert(job)
        assert dlq.count() == 1
        letters = dlq.list()
        assert letters[0]["job_id"] == job.id

    def test_replay(self):
        dlq = DeadLetterQueue()
        job = SyncJob(source="file:///test.txt")
        letter = dlq.insert(job)
        assert dlq.count() == 1
        replayed = dlq.replay(letter.id)
        assert replayed is not None
        assert dlq.count() == 0

    def test_delete(self):
        dlq = DeadLetterQueue()
        job = SyncJob(source="file:///test.txt")
        letter = dlq.insert(job)
        assert dlq.delete(letter.id)
        assert dlq.count() == 0
