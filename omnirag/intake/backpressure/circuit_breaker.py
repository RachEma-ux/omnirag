"""Circuit breaker — per-indexer, auto-open on failure, half-open recovery."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when circuit is open and call is rejected."""
    pass


class CircuitBreaker:
    """Per-indexer circuit breaker.

    - CLOSED: normal operation, counting failures
    - OPEN: all calls rejected (after failure_threshold reached)
    - HALF_OPEN: after timeout, allow one probe call
    """

    def __init__(self, name: str = "", failure_threshold: int = 5, timeout_seconds: float = 60) -> None:
        self.name = name
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: float | None = None
        self.threshold = failure_threshold
        self.timeout = timeout_seconds

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time > self.timeout):
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            result = func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.threshold:
                self.state = CircuitState.OPEN
            raise

    async def async_call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute async function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time > self.timeout):
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.threshold:
                self.state = CircuitState.OPEN
            raise

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "threshold": self.threshold,
            "timeout_seconds": self.timeout,
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerManager:
    """Manages circuit breakers for all indexers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, name: str, failure_threshold: int = 5, timeout_seconds: float = 60) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, failure_threshold, timeout_seconds)
        return self._breakers[name]

    def reset(self, name: str) -> bool:
        if name in self._breakers:
            self._breakers[name].reset()
            return True
        return False

    def get_all(self) -> dict[str, dict]:
        return {k: v.to_dict() for k, v in self._breakers.items()}

    def get_open(self) -> list[str]:
        return [k for k, v in self._breakers.items() if v.state == CircuitState.OPEN]


_manager = CircuitBreakerManager()


def get_circuit_manager() -> CircuitBreakerManager:
    return _manager
