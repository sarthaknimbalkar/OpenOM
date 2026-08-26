"""M3 Task 2: BlobStore interface + LocalBlobStore. TTL and delete-on-completion are proven with an
injected clock (no wall-clock), and per-principal authz (anti-IDOR, [OM-SEC-013]) returns OM-IO-007
for a foreign principal vs OM-IO-006 for missing/expired.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openom_mcp.blobstore import LocalBlobStore, new_blob_id
from openom_mcp.tools import ToolError


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _store(tmp_path: Path, clock: Clock | None = None, ttl: int = 86400) -> LocalBlobStore:
    return LocalBlobStore(tmp_path, ttl_seconds=ttl, now=clock or Clock())


def test_new_blob_id_is_unguessable() -> None:
    a, b = new_blob_id(), new_blob_id()
    assert a != b and len(a) >= 32  # >=128 bits of entropy, url-safe


def test_create_upload_returns_id_put_target_and_expiry(tmp_path: Path) -> None:
    s = _store(tmp_path)
    up = s.create_upload("ip:1.2.3.4")
    assert up["blobId"] and up["presignedPut"] and up["expiresAt"]


def test_put_and_get_round_trips_for_owner(tmp_path: Path) -> None:
    s = _store(tmp_path)
    res = s.put_result(b"%PDF-1.7 hello", "ip:1.2.3.4")
    assert s.get(res["blobId"], "ip:1.2.3.4") == b"%PDF-1.7 hello"


def test_get_unknown_raises_006(tmp_path: Path) -> None:
    s = _store(tmp_path)
    with pytest.raises(ToolError) as e:
        s.get("does-not-exist", "ip:1.2.3.4")
    assert e.value.code == "OM-IO-006"


def test_get_other_principal_raises_007(tmp_path: Path) -> None:
    s = _store(tmp_path)
    res = s.put_result(b"%PDF- x", "ip:owner")
    with pytest.raises(ToolError) as e:
        s.get(res["blobId"], "ip:attacker")
    assert e.value.code == "OM-IO-007"  # anti-IDOR: exists but not yours


def test_delete_removes_blob(tmp_path: Path) -> None:
    s = _store(tmp_path)
    res = s.put_result(b"%PDF- x", "ip:owner")
    s.delete(res["blobId"])
    with pytest.raises(ToolError) as e:
        s.get(res["blobId"], "ip:owner")
    assert e.value.code == "OM-IO-006"
    s.delete(res["blobId"])  # idempotent


def test_ttl_backstop_uses_injected_now(tmp_path: Path) -> None:
    clock = Clock(1000.0)
    s = _store(tmp_path, clock, ttl=86400)
    res = s.put_result(b"%PDF- x", "ip:owner")
    clock.t += 86400 + 1  # jump past the 24h TTL
    with pytest.raises(ToolError) as e:
        s.get(res["blobId"], "ip:owner")
    assert e.value.code == "OM-IO-006"


def test_produced_blobs_are_reaped_after_ttl_sweep_on_put(tmp_path: Path) -> None:
    # Round-3: produced result blobs / upload reservations are never routed to delete() by the tool
    # layer, and no local:// route triggers get()'s TTL backstop - so without sweep-on-put they leak
    # forever. A new put after the TTL must reap the stale ones (files + meta).
    clock = Clock(0.0)
    store = _store(tmp_path, clock, ttl=100)
    old = store.put_result(b"%PDF-old", "p")["blobId"]
    store.create_upload("p")  # a reservation also counts toward growth
    assert len(store._meta) == 2
    assert (tmp_path / old).exists()
    clock.t += 101  # everything is now past TTL
    store.put_result(b"%PDF-new", "p")  # triggers the sweep
    assert len(store._meta) == 1  # only the fresh blob remains
    assert not (tmp_path / old).exists()  # the stale file was reaped
