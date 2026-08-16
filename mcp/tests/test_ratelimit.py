"""M3 Task 3: principal extraction + per-principal rate limiting ([OM-SEC-012]). The limiter uses an
injected clock so window resets are deterministic; over-limit raises OM-IO-014 with retryAfter.
"""

from __future__ import annotations

import pytest

from openom_mcp.principal import extract_principal
from openom_mcp.ratelimit import InMemoryRateLimiter
from openom_mcp.tools import ToolError


class Clock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_bearer_token_becomes_key_principal() -> None:
    p = extract_principal({"Authorization": "Bearer sk-abc123"}, "1.2.3.4")
    assert p.startswith("key:") and "sk-abc123" not in p  # hashed, not the raw token


def test_no_auth_falls_back_to_ip() -> None:
    assert extract_principal({}, "1.2.3.4") == "ip:1.2.3.4"


def test_header_case_insensitive() -> None:
    assert extract_principal({"authorization": "Bearer x"}, "1.2.3.4").startswith("key:")


def test_limiter_allows_under_limit() -> None:
    rl = InMemoryRateLimiter(limit=3, window_seconds=60, now=Clock())
    for _ in range(3):
        rl.check("ip:a")  # no raise


def test_limiter_blocks_over_limit_with_retry() -> None:
    clock = Clock(0.0)
    rl = InMemoryRateLimiter(limit=2, window_seconds=60, now=clock)
    rl.check("ip:a")
    rl.check("ip:a")
    with pytest.raises(ToolError) as e:
        rl.check("ip:a")
    assert e.value.code == "OM-IO-014"
    assert e.value.retry_after is not None and e.value.retry_after > 0
    assert e.value.retryable is True


def test_principals_are_independent() -> None:
    rl = InMemoryRateLimiter(limit=1, window_seconds=60, now=Clock())
    rl.check("ip:a")
    rl.check("ip:b")  # different principal, own bucket -> no raise


def test_window_resets_with_injected_now() -> None:
    clock = Clock(0.0)
    rl = InMemoryRateLimiter(limit=1, window_seconds=60, now=clock)
    rl.check("ip:a")
    clock.t += 61  # next window
    rl.check("ip:a")  # allowed again
