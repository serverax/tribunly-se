"""Minimal, dependency-free circuit breaker for external dependencies.

Scale contract: at 100k concurrent, a failing external dependency (e.g. the
Ollama inference fabric) must NOT cause every request to pile up on a slow/dead
socket. After `fail_max` consecutive failures the breaker OPENS and subsequent
calls fail FAST with CircuitOpenError (caller maps this to a controlled 503 /
graceful degradation) instead of blocking. After `reset_timeout_s` the breaker
goes HALF_OPEN and lets a single trial through; success closes it, failure
re-opens it.

Thread-safe. The clock is injectable so behaviour is deterministically testable
without sleeping (Date/time helpers are unavailable in some sandboxes; tests pass
a fake monotonic clock).
"""
from __future__ import annotations

import threading
from typing import Callable

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the breaker is OPEN (fail-fast)."""


class CircuitBreaker:
    def __init__(self, name: str, *, fail_max: int = 5, reset_timeout_s: float = 30.0,
                 clock: Callable[[], float] | None = None):
        if fail_max < 1:
            raise ValueError("fail_max must be >= 1")
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout_s = reset_timeout_s
        self._clock = clock or self._default_clock
        self._lock = threading.Lock()
        self._state = CLOSED
        self._fail_count = 0
        self._opened_at = 0.0

    @staticmethod
    def _default_clock() -> float:
        import time
        return time.monotonic()

    @property
    def state(self) -> str:
        # Resolve a due OPEN->HALF_OPEN transition on read.
        with self._lock:
            return self._state_locked()

    def _state_locked(self) -> str:
        if self._state == OPEN and (self._clock() - self._opened_at) >= self.reset_timeout_s:
            self._state = HALF_OPEN
        return self._state

    def _on_success(self) -> None:
        with self._lock:
            self._fail_count = 0
            self._state = CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._fail_count += 1
            if self._state == HALF_OPEN or self._fail_count >= self.fail_max:
                self._state = OPEN
                self._opened_at = self._clock()

    def call(self, fn: Callable, *args, **kwargs):
        """Run fn under the breaker. Raises CircuitOpenError when OPEN."""
        with self._lock:
            state = self._state_locked()
            if state == OPEN:
                raise CircuitOpenError(f"circuit '{self.name}' is open")
            # HALF_OPEN: allow exactly this trial through (still counts).
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result
