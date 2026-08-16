"""M3 Task 4: PdfResolver enforces the transport policy — path only on stdio, url/blobId only on
http, exactly one key. Deterministic tool bodies stay unchanged; only PDF resolution differs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openom_mcp.resolve import PdfResolver
from openom_mcp.tools import ToolError


class FakeFetcher:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def get(self, url: str) -> bytes:
        self.seen.append(url)
        return b"%PDF- from url"


class FakeBlobStore:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str | None]] = []

    def get(self, blob_id: str, principal: str) -> bytes:
        self.seen.append((blob_id, principal))
        return b"%PDF- from blob"


def test_stdio_path_ok(tmp_path: Path) -> None:
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF- local")
    r = PdfResolver(transport="stdio")
    assert r.resolve({"path": str(p)}) == b"%PDF- local"


def test_stdio_url_and_blob_rejected() -> None:
    r = PdfResolver(transport="stdio")
    for ref in ({"url": "https://h/x"}, {"blobId": "abc"}):
        with pytest.raises(ToolError) as e:
            r.resolve(ref)
        assert e.value.code == "OM-IO-008"


def test_http_path_rejected() -> None:
    r = PdfResolver(transport="http", fetcher=FakeFetcher(), blobstore=FakeBlobStore())
    with pytest.raises(ToolError) as e:
        r.resolve({"path": "/etc/passwd"})
    assert e.value.code == "OM-IO-008"


def test_http_url_calls_fetcher() -> None:
    f = FakeFetcher()
    r = PdfResolver(transport="http", fetcher=f, blobstore=FakeBlobStore())
    assert r.resolve({"url": "https://h/x"}) == b"%PDF- from url"
    assert f.seen == ["https://h/x"]


def test_http_blob_calls_blobstore_with_principal() -> None:
    b = FakeBlobStore()
    r = PdfResolver(transport="http", fetcher=FakeFetcher(), blobstore=b)
    assert r.resolve({"blobId": "bid"}, principal="ip:1.2.3.4") == b"%PDF- from blob"
    assert b.seen == [("bid", "ip:1.2.3.4")]


def test_multiple_keys_rejected() -> None:
    r = PdfResolver(transport="stdio")
    with pytest.raises(ToolError) as e:
        r.resolve({"path": "/x", "url": "https://h/x"})
    assert e.value.code == "OM-IO-008"


def test_non_dict_rejected() -> None:
    r = PdfResolver(transport="stdio")
    with pytest.raises(ToolError) as e:
        r.resolve("not-a-ref")  # type: ignore[arg-type]
    assert e.value.code == "OM-IO-008"
