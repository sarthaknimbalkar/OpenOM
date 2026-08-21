"""M3 Task 8: S3/R2 BlobStore adapter - integration only. SKIPPED unless the OPENOM_R2_* env is set
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
    reason="R2/MinIO env not set (OPENOM_R2_*) - integration-only",
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


def test_r2_owner_is_server_bound_not_client_metadata() -> None:
    # #50: ownership is recorded by the server-written _owners/<id> object, so a presigned upload
    # (which covers only the data key) cannot forge or omit it. Simulate a raw data-only PUT to a
    # created-upload slot and confirm the real owner still governs authz.
    s = _store()
    slot = s.create_upload("ip:owner")
    bid = slot["blobId"]
    try:
        s.s3.put_object(Bucket=s.bucket, Key=bid, Body=b"%PDF- uploaded")  # client PUT, no metadata
        assert s.get(bid, "ip:owner") == b"%PDF- uploaded"  # server-bound owner still works
        with pytest.raises(ToolError) as e:
            s.get(bid, "ip:attacker")
        assert e.value.code == "OM-IO-007"
    finally:
        s.delete(bid)
