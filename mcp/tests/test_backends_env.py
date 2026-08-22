"""[Ma7] Production blob/limiter backends are selectable from the environment."""

from __future__ import annotations

import sys
import types

import pytest

from openom_mcp.server import backends_from_env


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for k in list(os.environ):
        if k.startswith(("OPENOM_MCP_", "OPENOM_R2_", "OPENOM_REDIS_")):
            monkeypatch.delenv(k, raising=False)


def test_defaults_select_no_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    assert backends_from_env(120, 60) == {}


def test_r2_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENOM_MCP_BLOB_BACKEND", "r2")
    with pytest.raises(SystemExit):
        backends_from_env(120, 60)


def test_redis_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENOM_MCP_LIMITER", "redis")
    with pytest.raises(SystemExit):
        backends_from_env(120, 60)


def test_r2_backend_is_constructed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENOM_MCP_BLOB_BACKEND", "r2")
    monkeypatch.setenv("OPENOM_R2_BUCKET", "om-blobs")
    seen = {}

    class FakeStore:
        def __init__(self, **kw: object) -> None:
            seen.update(kw)

    monkeypatch.setattr("openom_mcp.blobstore.S3BlobStore", FakeStore)
    out = backends_from_env(120, 60)
    assert isinstance(out["blob_store"], FakeStore)
    assert seen["bucket"] == "om-blobs"


def test_redis_limiter_is_constructed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENOM_MCP_LIMITER", "redis")
    monkeypatch.setenv("OPENOM_REDIS_URL", "redis://localhost:6379/0")
    fake_redis = types.ModuleType("redis")
    fake_redis.from_url = lambda url: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "redis", fake_redis)
    out = backends_from_env(10, 5)
    from openom_mcp.ratelimit import DistributedRateLimiter

    assert isinstance(out["rate_limiter"], DistributedRateLimiter)
    assert out["rate_limiter"].limit == 10
