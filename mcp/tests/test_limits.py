"""M3 #49: per-call page ceiling ([OM-MCP-008]). A document exceeding the limit returns a mapped
OM-IO-005 (never a silent truncation), enforced on the hosted transport inside the bounded parse.
Stdio is trusted-local and unbounded.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest

from openom_mcp import tools
from openom_mcp.blobstore import LocalBlobStore
from openom_mcp.resolve import PdfResolver

PRINCIPAL = "ip:1.2.3.4"


def _pdf(pages: int) -> bytes:
    doc = pikepdf.new()
    for _ in range(pages):
        doc.add_blank_page(page_size=(200, 200))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def http(tmp_path: Path):
    store = LocalBlobStore(tmp_path)
    tools.set_resolver(PdfResolver(transport="http", blobstore=store))
    tools.set_rate_limiter(None)
    token = tools._current_principal.set(PRINCIPAL)
    yield store
    tools._current_principal.reset(token)
    tools.set_resolver(None)


def test_over_page_limit_rejected(http: LocalBlobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "_MAX_PAGES", 1)
    bid = http.put_result(_pdf(3), PRINCIPAL)["blobId"]
    res = tools.om_inspect({"blobId": bid})
    assert res["error"]["code"] == "OM-IO-005"


def test_within_page_limit_ok(http: LocalBlobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "_MAX_PAGES", 10)
    bid = http.put_result(_pdf(2), PRINCIPAL)["blobId"]
    res = tools.om_inspect({"blobId": bid})
    assert "error" not in res and res["class"] in {"native", "hybrid", "scanned"}


def test_stdio_ignores_page_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tools.set_resolver(PdfResolver(transport="stdio"))
    monkeypatch.setattr(tools, "_MAX_PAGES", 1)
    p = tmp_path / "many.pdf"
    p.write_bytes(_pdf(5))
    try:
        res = tools.om_inspect({"path": str(p)})
        assert "error" not in res  # trusted-local: no ceiling
    finally:
        tools.set_resolver(None)
