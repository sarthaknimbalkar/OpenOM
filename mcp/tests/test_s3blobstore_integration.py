"""M3 Task 8: S3/R2 BlobStore adapter — integration only. SKIPPED unless the OPENOM_R2_* env is set
(a real R2 bucket or a local MinIO), so CI stays offline. Run locally against MinIO to exercise the
same interface LocalBlobStore proves in the gate: put -> get -> delete, plus foreign-principal 007.
"""

from __future__ import annotations

import os

import pytest

from openom_mcp.blobstore import S3BlobStore
from openom_mcp.tools import ToolError

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENOM_R2_BUCKET"),
    reason="R2/MinIO env not set (OPENOM_R2_*) — integration-only",
)


def _store() -> S3BlobStore:
    return S3BlobStore(
        bucket=os.environ["OPENOM_R2_BUCKET"],
        endpoint_url=os.environ["OPENOM_R2_ENDPOINT"],
        access_key=os.environ["OPENOM_R2_KEY"],
        secret_key=os.environ["OPENOM_R2_SECRET"],
    )


def test_r2_round_trip_and_delete() -> None:
    s = _store()
    res = s.put_result(b"%PDF- r2 payload", "ip:owner")
    assert s.get(res["blobId"], "ip:owner") == b"%PDF- r2 payload"
    s.delete(res["blobId"])
    with pytest.raises(ToolError) as e:
        s.get(res["blobId"], "ip:owner")
    assert e.value.code == "OM-IO-006"


def test_r2_foreign_principal_rejected() -> None:
    s = _store()
    res = s.put_result(b"%PDF- r2", "ip:owner")
    try:
        with pytest.raises(ToolError) as e:
            s.get(res["blobId"], "ip:attacker")
        assert e.value.code == "OM-IO-007"
    finally:
        s.delete(res["blobId"])
