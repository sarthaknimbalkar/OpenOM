"""#51/#52: the Redis-backed CounterStore, proven against fakeredis so the algorithm is verified
without a live server — the hosted deploy swaps in a real redis-py client at the same seam."""

from __future__ import annotations

import fakeredis
import pytest

from openom_mcp.apikeys import ApiKeyManager, InMemoryKeyStore
from openom_mcp.ratelimit import DistributedRateLimiter
from openom_mcp.redisstore import RedisCounterStore
from openom_mcp.tools import ToolError


def _store() -> RedisCounterStore:
    return RedisCounterStore(fakeredis.FakeStrictRedis())


def test_incr_counts_and_arms_a_ttl_on_first_hit() -> None:
    client = fakeredis.FakeStrictRedis()
    store = RedisCounterStore(client)
    assert store.incr("k", 60) == 1
    assert store.incr("k", 60) == 2
    assert 0 < client.ttl("k") <= 60  # TTL was set on the first increment, so the window expires


def test_distributed_limiter_over_redis_enforces_the_window() -> None:
    limiter = DistributedRateLimiter(_store(), limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("ip:1.2.3.4")
    with pytest.raises(ToolError) as e:
        limiter.check("ip:1.2.3.4")
    assert e.value.code == "OM-IO-014"


def test_two_replicas_share_one_redis_global_limit() -> None:
    client = fakeredis.FakeStrictRedis()  # one Redis, two limiter "replicas"
    a = DistributedRateLimiter(RedisCounterStore(client), limit=2, window_seconds=60)
    b = DistributedRateLimiter(RedisCounterStore(client), limit=2, window_seconds=60)
    a.check("ip:x")
    b.check("ip:x")
    with pytest.raises(ToolError):
        a.check("ip:x")  # the 3rd call at EITHER replica is over the shared limit


def test_api_key_quota_over_redis() -> None:
    store = _store()
    mgr = ApiKeyManager(InMemoryKeyStore(), store)
    _, rec = mgr.issue("acme", quota_limit=2, quota_window_seconds=3600)
    mgr.check_quota(rec)
    mgr.check_quota(rec)
    with pytest.raises(ToolError):
        mgr.check_quota(rec)  # per-key quota enforced through the same Redis counter
