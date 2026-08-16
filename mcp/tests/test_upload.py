"""M3 Task 5: om_request_upload + om_embed blob output + delete-on-completion. Uses an http-wired
resolver over LocalBlobStore; the deterministic tool bodies are unchanged, only input/output I/O.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pytest

from openom_mcp import tools
from openom_mcp.blobstore import LocalBlobStore
from openom_mcp.resolve import PdfResolver

SPEC = Path(__file__).resolve().parents[2] / "spec"
SAMPLE = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
PRINCIPAL = "ip:1.2.3.4"


def _blank_pdf() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


@pytest.fixture
def http_store(tmp_path: Path):
    store = LocalBlobStore(tmp_path)
    tools.set_resolver(PdfResolver(transport="http", blobstore=store))
    token = tools._current_principal.set(PRINCIPAL)
    yield store
    tools._current_principal.reset(token)
    tools.set_resolver(None)


def test_request_upload_stdio_rejected() -> None:
    tools.set_resolver(PdfResolver(transport="stdio"))
    try:
        res = tools.om_request_upload()
        assert res["error"]["code"] == "OM-IO-008"
    finally:
        tools.set_resolver(None)


def test_request_upload_returns_put_target(http_store: LocalBlobStore) -> None:
    res = tools.om_request_upload()
    assert res["blobId"] and res["presignedPut"] and res["expiresAt"]


def test_embed_http_returns_blob_output(http_store: LocalBlobStore) -> None:
    inp = http_store.put_result(_blank_pdf(), PRINCIPAL)["blobId"]
    res = tools.om_embed({"blobId": inp}, SAMPLE)
    assert "blobId" in res["pdf"] and "path" not in res["pdf"]
    assert res["pdf"]["presignedGet"]
    # the output blob is retrievable
    assert http_store.get(res["pdf"]["blobId"], PRINCIPAL).startswith(b"%PDF-")


def test_input_blob_deleted_after_call(http_store: LocalBlobStore) -> None:
    inp = http_store.put_result(_blank_pdf(), PRINCIPAL)["blobId"]
    tools.om_read({"blobId": inp})  # consumes the input blob
    res = tools.om_inspect({"blobId": inp})  # second use must now fail: blob was deleted
    assert res["error"]["code"] == "OM-IO-006"
