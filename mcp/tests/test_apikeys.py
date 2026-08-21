"""#52 API-key lifecycle (issue/verify/rotate/revoke + per-key quota) and #51 distributed limiter.
All logic is deterministic over injected clock + in-memory store/counters, so the algorithm is
proven without a live Redis/KV - the hosted deploy binds real backends to the same seams.
"""

from __future__ import annotations

import pytest

from openom_mcp.apikeys import KEY_PREFIX, ApiKeyManager, InMemoryKeyStore, hash_key
from openom_mcp.ratelimit import (
    DistributedRateLimiter,
    InMemoryCounterStore,
)
from openom_mcp.tools import ToolError


class Clock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _manager(clock: Clock) -> ApiKeyManager:
    seq = iter(f"tok{i}" for i in range(1000))
    return ApiKeyManager(
        InMemoryKeyStore(), InMemoryCounterStore(now=clock), now=clock, rng=lambda: next(seq)
    )


# --- #52: issue / verify / revoke / rotate -------------------------------------------------------
def test_issue_returns_plaintext_once_and_stores_only_the_hash() -> None:
    mgr = _manager(Clock())
    plaintext, record = mgr.issue("acme")
    assert plaintext.startswith(KEY_PREFIX)
    assert record.key_hash == hash_key(plaintext)
    assert record.owner == "acme" and record.status == "active"
    # The store never holds the plaintext - only its hash resolves a record.
    assert mgr.store.get_by_hash(hash_key(plaintext)) is record


def test_verify_accepts_active_rejects_unknown_and_malformed() -> None:
    mgr = _manager(Clock())
    plaintext, _ = mgr.issue("acme")
    assert mgr.verify(plaintext) is not None
    assert mgr.verify("omk_never-issued") is None
    assert mgr.verify("not-an-openom-key") is None  # missing prefix


def test_revoke_is_immediate() -> None:
    mgr = _manager(Clock())
    plaintext, record = mgr.issue("acme")
    assert mgr.revoke(record.key_id) is True
    assert mgr.verify(plaintext) is None  # revoked → no longer verifies
    assert mgr.revoke(record.key_id) is False  # idempotent: already revoked
    assert mgr.revoke("k_missing") is False


def test_rotate_issues_new_and_revokes_old_preserving_policy() -> None:
    mgr = _manager(Clock())
    old_plain, old = mgr.issue("acme", quota_limit=500, quota_window_seconds=3600)
    rotated = mgr.rotate(old.key_id)
    assert rotated is not None
    new_plain, new = rotated
    assert new_plain != old_plain and new.owner == "acme"
    assert new.quota_limit == 500 and new.quota_window_seconds == 3600  # policy carried
    assert mgr.verify(old_plain) is None and mgr.verify(new_plain) is not None
    assert mgr.rotate("k_missing") is None


# --- #52: per-key quota --------------------------------------------------------------------------
def test_quota_caps_calls_per_window_then_resets() -> None:
    clock = Clock(0.0)
    mgr = _manager(clock)
    _, rec = mgr.issue("acme", quota_limit=2, quota_window_seconds=100)
    mgr.check_quota(rec)  # 1
    mgr.check_quota(rec)  # 2
    with pytest.raises(ToolError) as e:
        mgr.check_quota(rec)  # 3 → over
    assert e.value.code == "OM-IO-014" and e.value.retry_after is not None
    clock.t = 100.0  # next window
    mgr.check_quota(rec)  # allowed again


def test_zero_quota_is_unlimited() -> None:
    mgr = _manager(Clock())
    _, rec = mgr.issue("acme", quota_limit=0)
    for _ in range(50):
        mgr.check_quota(rec)  # never raises


# --- #51: distributed rate limiter over a shared counter -----------------------------------------
def test_distributed_limiter_enforces_a_window() -> None:
    clock = Clock(0.0)
    limiter = DistributedRateLimiter(
        InMemoryCounterStore(now=clock), limit=3, window_seconds=60, now=clock
    )
    for _ in range(3):
        limiter.check("ip:1.2.3.4")
    with pytest.raises(ToolError) as e:
        limiter.check("ip:1.2.3.4")
    assert e.value.code == "OM-IO-014" and e.value.retryable is True
    clock.t = 60.0  # new window
    limiter.check("ip:1.2.3.4")  # allowed


def test_distributed_limiter_is_per_principal() -> None:
    limiter = DistributedRateLimiter(InMemoryCounterStore(), limit=1, window_seconds=60)
    limiter.check("ip:a")
    limiter.check("ip:b")  # a different principal has its own budget
    with pytest.raises(ToolError):
        limiter.check("ip:a")


def test_distributed_limiter_shares_one_store_across_instances() -> None:
    # Two limiter instances (simulating two server replicas) over ONE counter store enforce a single
    # global limit - the whole point of #51.
    clock = Clock(0.0)
    store = InMemoryCounterStore(now=clock)
    a = DistributedRateLimiter(store, limit=2, window_seconds=60, now=clock)
    b = DistributedRateLimiter(store, limit=2, window_seconds=60, now=clock)
    a.check("ip:x")
    b.check("ip:x")
    with pytest.raises(ToolError):
        a.check("ip:x")  # the 3rd call anywhere is over the shared limit
