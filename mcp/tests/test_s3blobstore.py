"""M3 #50: S3BlobStore owner-binding, verified offline against a mocked S3 (moto) - no network, no
MinIO. Proves ownership is SERVER-bound (a raw client PUT without metadata cannot forge/omit it),
foreign principals get OM-IO-007, missing/deleted → OM-IO-006. Skips where moto is absent; #53
wires moto into CI so this runs there.
"""

from __future__ import annotations

import pytest

moto = pytest.importorskip("moto")
import boto3  # noqa: E402

from openom_mcp.blobstore import S3BlobStore  # noqa: E402
from openom_mcp.tools import ToolError  # noqa: E402

BUCKET = "openom-test-bucket"


@pytest.fixture
def store():
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield S3BlobStore(bucket=BUCKET, client=client), client


def test_put_get_round_trip_and_authz(store) -> None:
    s, _ = store
    res = s.put_result(b"%PDF- data", "ip:owner")
    assert s.get(res["blobId"], "ip:owner") == b"%PDF- data"
    with pytest.raises(ToolError) as e:
        s.get(res["blobId"], "ip:attacker")
    assert e.value.code == "OM-IO-007"


def test_owner_is_server_bound_not_client_metadata(store) -> None:
    s, client = store
    slot = s.create_upload("ip:owner")
    bid = slot["blobId"]
    client.put_object(Bucket=BUCKET, Key=bid, Body=b"%PDF- uploaded")  # raw PUT, no owner metadata
    assert s.get(bid, "ip:owner") == b"%PDF- uploaded"  # server-written owner still governs
    with pytest.raises(ToolError) as e:
        s.get(bid, "ip:attacker")
    assert e.value.code == "OM-IO-007"  # cannot be forged/omitted via the data PUT


def test_missing_blob_is_006(store) -> None:
    s, _ = store
    with pytest.raises(ToolError) as e:
        s.get("does-not-exist", "ip:owner")
    assert e.value.code == "OM-IO-006"


def test_delete_removes_data_and_owner(store) -> None:
    s, _ = store
    bid = s.put_result(b"%PDF- x", "ip:owner")["blobId"]
    s.delete(bid)
    with pytest.raises(ToolError) as e:
        s.get(bid, "ip:owner")
    assert e.value.code == "OM-IO-006"
