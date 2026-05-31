"""Circuit breaker for LLM and tool calls — prevents cascading failures."""

import time
from collections import defaultdict

from config import settings


class CircuitBreaker:
    """Simple sliding-window circuit breaker.

    When consecutive failures exceed the threshold within the time window,
    the circuit opens and rejects further requests until the window resets.
    """

    def __init__(self, name: str):
        self.name = name
        self._failures: list[float] = []  # timestamps of failures
        self._open_at: float | None = None  # when the circuit was opened

    @property
    def is_open(self) -> bool:
        """Return True if the circuit is currently open (rejecting requests)."""
        if self._open_at is None:
            return False
        # Auto-reset after window expires
        if time.monotonic() - self._open_at > settings.circuit_breaker_window:
            self._open_at = None
            self._failures.clear()
            return False
        return True

    def record_success(self) -> None:
        """Record a successful call — resets the failure window."""
        self._failures.clear()
        self._open_at = None

    def record_failure(self) -> None:
        """Record a failed call. Opens the circuit if threshold exceeded."""
        now = time.monotonic()
        self._failures.append(now)
        # Prune old failures outside window
        cutoff = now - settings.circuit_breaker_window
        self._failures = [t for t in self._failures if t > cutoff]
        # Check threshold
        if len(self._failures) >= settings.circuit_breaker_failures:
            self._open_at = now


# Global circuit breakers per component
breakers: dict[str, CircuitBreaker] = defaultdict(lambda: CircuitBreaker("default"))


def get_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for the given component."""
    if name not in breakers:
        breakers[name] = CircuitBreaker(name)
    return breakers[name]
