# SPDX-License-Identifier: MIT
"""Redis-backed CounterStore for the distributed rate limiter / quota (#51, #52).

Binds the ``CounterStore`` seam (ratelimit.py) to a Redis-compatible client so every server
replica sharing one Redis enforces a single global count per window. ``incr`` = ``INCR`` then,
only on the FIRST increment of a window, ``EXPIRE`` to arm the TTL — the standard atomic-counter
idiom that works on real Redis and fakeredis alike. (A process crash in the microseconds between
INCR and EXPIRE would leave one window key without a TTL; it is a distinct key per window index,
so it never blocks the next window — it just lingers in memory.)

The client is INJECTED (redis-py, fakeredis, or an Upstash/edge client): this module imports no
redis package, so ``/mcp`` gains no hard runtime dependency — the hosted deploy passes a real
client, tests pass a fake one. Deterministic and inference-free.
"""

from __future__ import annotations

from typing import Any


class RedisCounterStore:
    """A ``CounterStore`` (see ratelimit.CounterStore) over an injected Redis-compatible client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def incr(self, key: str, ttl_seconds: int) -> int:
        value = int(self._client.incr(key))
        if value == 1:  # first hit of this window → arm the expiry
            self._client.expire(key, ttl_seconds)
        return value
