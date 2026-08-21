# SPDX-License-Identifier: MIT
"""Per-principal rate limiting for the hosted transport ([OM-SEC-012]).

``RateLimiter`` is the interface; ``InMemoryRateLimiter`` is a fixed-window counter with an injected
clock (deterministic in tests). Over-limit raises ToolError OM-IO-014 with ``retry_after`` seconds.
Rate limiting only bounds resource use - it never weakens a correctness/verification guarantee.
``DistributedRateLimiter`` (#51) implements the same interface over a shared ``CounterStore`` (Redis
INCR/EXPIRE or a Durable Object), so a multi-instance deploy enforces one global limit per
principal; ``InMemoryCounterStore`` fakes that store for tests/self-host.
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Protocol

from .tools import ToolError


class CounterStore(Protocol):
    """A shared atomic counter - the one primitive a distributed limiter/quota needs (#51).

    ``incr`` increments the counter at ``key``, sets a TTL of ``ttl_seconds`` on the FIRST increment
    (so windows self-expire), and returns the new value. Redis ``INCR``+``EXPIRE`` and a Durable
    Object's transactional storage each implement this exactly; ``InMemoryCounterStore`` fakes it
    for tests/self-host.
    """

    def incr(self, key: str, ttl_seconds: int) -> int: ...


class InMemoryCounterStore:
    """A single-process CounterStore mirroring Redis INCR/EXPIRE semantics (tests/self-host)."""

    def __init__(self, *, now: Callable[[], float] = time.time) -> None:
        self.now = now
        self._v: dict[str, tuple[int, float]] = {}  # key -> (count, expires_at)

    def incr(self, key: str, ttl_seconds: int) -> int:
        t = self.now()
        count, expires = self._v.get(key, (0, 0.0))
        if t >= expires:  # absent or expired → fresh window, (re)arm the TTL
            count, expires = 0, t + ttl_seconds
        count += 1
        self._v[key] = (count, expires)
        return count


def _retry_after(now: float, window: int) -> int:
    return max(1, math.ceil(window - (now % window)))


class RateLimiter(ABC):
    @abstractmethod
    def check(self, principal: str) -> None:
        """Allow (return) or deny (raise ToolError OM-IO-014 with retry_after)."""


class DistributedRateLimiter(RateLimiter):
    """Fixed-window limiter over a shared CounterStore, so a multi-instance deploy enforces ONE
    global limit per principal (#51). Same window math as InMemoryRateLimiter; the difference is the
    counter lives in Redis / a Durable Object, not process memory."""

    def __init__(
        self,
        store: CounterStore,
        *,
        limit: int,
        window_seconds: int,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.limit = limit
        self.window = window_seconds
        self.now = now

    def check(self, principal: str) -> None:
        t = self.now()
        idx = int(t // self.window)
        count = self.store.incr(f"rl:{principal}:{idx}", self.window)
        if count > self.limit:
            raise ToolError(
                "OM-IO-014", "rate limit exceeded", retryable=True,
                retry_after=_retry_after(t, self.window),
            )


class InMemoryRateLimiter(RateLimiter):
    """Fixed-window: at most ``limit`` calls per ``window_seconds`` per principal."""

    def __init__(
        self, *, limit: int, window_seconds: int, now: Callable[[], float] = time.time
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self.now = now
        self._windows: dict[str, tuple[int, int]] = {}  # principal -> (window_index, count)

    def check(self, principal: str) -> None:
        idx = int(self.now() // self.window)
        cur_idx, count = self._windows.get(principal, (idx, 0))
        if cur_idx != idx:  # a new window started
            cur_idx, count = idx, 0
        if count >= self.limit:
            elapsed = self.now() - cur_idx * self.window
            retry_after = max(1, math.ceil(self.window - elapsed))
            raise ToolError(
                "OM-IO-014", "rate limit exceeded", retryable=True, retry_after=retry_after
            )
        self._windows[principal] = (cur_idx, count + 1)
