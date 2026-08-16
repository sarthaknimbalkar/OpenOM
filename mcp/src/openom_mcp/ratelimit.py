# SPDX-License-Identifier: MIT
"""Per-principal rate limiting for the hosted transport ([OM-SEC-012]).

``RateLimiter`` is the interface; ``InMemoryRateLimiter`` is a fixed-window counter with an injected
clock (deterministic in tests). Over-limit raises ToolError OM-IO-014 with ``retry_after`` seconds.
Rate limiting only bounds resource use — it never weakens a correctness/verification guarantee.
A Redis/Durable-Object limiter can implement the same interface later.
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from .tools import ToolError


class RateLimiter(ABC):
    @abstractmethod
    def check(self, principal: str) -> None:
        """Allow (return) or deny (raise ToolError OM-IO-014 with retry_after)."""


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
