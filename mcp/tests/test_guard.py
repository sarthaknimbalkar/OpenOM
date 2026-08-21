"""M3 #45: bounded_call mechanism ([OM-SEC-010]). Uses stdlib/builtin targets (importable in the
spawned child regardless of pytest) to prove: ok passthrough, in-child exception → OM-IO-010, hard
process crash → OM-IO-010, and a hung call killed on the wall-clock → OM-IO-003.
"""

from __future__ import annotations

import os
import time

import pytest

from openom_mcp.guard import _RESOURCE_AVAILABLE, bounded_call
from openom_mcp.tools import ToolError


def test_ok_passthrough() -> None:
    assert bounded_call(abs, (-5,), timeout=30) == 5


def test_in_child_exception_maps_to_010() -> None:
    with pytest.raises(ToolError) as e:
        bounded_call(int, ("not-an-int",), timeout=30)  # raises ValueError in the child
    assert e.value.code == "OM-IO-010"


def test_hard_crash_maps_to_010() -> None:
    with pytest.raises(ToolError) as e:
        bounded_call(os._exit, (1,), timeout=30)  # child dies without returning
    assert e.value.code == "OM-IO-010"


@pytest.mark.skipif(not _RESOURCE_AVAILABLE, reason="RLIMIT_AS is POSIX-only")
def test_memory_cap_enforced_not_swallowed() -> None:
    # #123: under a 1 MB address-space cap, allocating ~64 MB in the child MUST fail (MemoryError),
    # surfacing as OM-IO-010 - proving the cap is applied and a breach is not silently swallowed.
    with pytest.raises(ToolError) as e:
        bounded_call(bytearray, (64 * 1024 * 1024,), timeout=30, memory_mb=1)
    assert e.value.code == "OM-IO-010"


def test_timeout_maps_to_003_and_is_killed() -> None:
    start = time.monotonic()
    with pytest.raises(ToolError) as e:
        bounded_call(time.sleep, (30,), timeout=1.0)  # hung child, killed at 1s
    assert e.value.code == "OM-IO-003"
    assert e.value.retryable is True
    assert time.monotonic() - start < 10  # actually terminated, not waited out
