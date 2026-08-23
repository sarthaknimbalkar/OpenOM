"""M3 Task 6 - the remote gate [OM-DoD-004]. Proves: the Streamable HTTP app builds and a real
in-process MCP session serves the full tool surface; the transport-aware I/O behaviors (path
rejected on http, url via SafeFetcher, blob upload→read round-trip, TTL + delete-on-completion,
rate-limit OM-IO-014, foreign-principal OM-IO-007); and the principal middleware. Fully offline.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import anyio
import pikepdf
import pytest
from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from openom_mcp import server, tools
from openom_mcp.blobstore import LocalBlobStore
from openom_mcp.ratelimit import InMemoryRateLimiter
from openom_mcp.resolve import PdfResolver

SPEC = Path(__file__).resolve().parents[2] / "spec"
SAMPLE = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
PRINCIPAL = "ip:9.9.9.9"


def _blank_pdf() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeFetcher:
    def get(self, url: str) -> bytes:
        return _blank_pdf()


@pytest.fixture
def http(tmp_path: Path):
    clock = Clock()
    store = LocalBlobStore(tmp_path, now=clock)
    tools.set_resolver(PdfResolver(transport="http", fetcher=FakeFetcher(), blobstore=store))
    tools.set_rate_limiter(None)
    token = tools._current_principal.set(PRINCIPAL)
    yield store, clock
    tools._current_principal.reset(token)
    tools.set_resolver(None)
    tools.set_rate_limiter(None)


# ---- transport serves the surface (real in-process MCP session) ----

def test_streamable_http_app_builds() -> None:
    app = server.build_http_app(blob_root=Path.cwd() / ".pytest-blobs-unused")
    assert callable(app)  # an ASGI app
    tools.set_resolver(None)
    tools.set_rate_limiter(None)


def test_session_serves_full_tool_surface() -> None:
    async def run() -> list[str]:
        async with InMemoryTransport(server.mcp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return [t.name for t in (await session.list_tools()).tools]

    names = anyio.run(run)
    for expected in (
        "om_inspect", "om_read", "om_extract_text", "om_extract_images",
        "om_validate", "om_embed", "om_request_upload",
    ):
        assert expected in names


def test_session_validate_round_trip() -> None:
    async def run() -> dict:
        async with InMemoryTransport(server.mcp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool("om_validate", {"payload": SAMPLE})
                return json.loads(res.content[0].text)  # type: ignore[union-attr]

    out = anyio.run(run)
    assert out["ok"] is True


# ---- transport-aware I/O behaviors (wired tool layer) ----

def test_path_rejected_on_http(http) -> None:
    res = tools.om_read({"path": "/etc/passwd"})
    assert res["error"]["code"] == "OM-IO-008"


def test_url_ref_fetched(http) -> None:
    res = tools.om_inspect({"url": "https://example.com/x.pdf"})
    assert "error" not in res and res["class"] in {"native", "hybrid", "scanned"}


def test_upload_then_read_round_trip(http) -> None:
    store, _ = http
    # simulate the client PUT: request an upload slot, then place bytes at that blobId
    slot = tools.om_request_upload()
    (store.root / slot["blobId"]).write_bytes(_embed_sample())  # simulate the client PUT
    res = tools.om_read({"blobId": slot["blobId"]})
    assert res["payload"] is not None and res["verification"]["hashValid"] is True


def test_blob_ttl_expiry(http) -> None:
    store, clock = http
    bid = store.put_result(_blank_pdf(), PRINCIPAL)["blobId"]
    clock.t += 86400 + 1
    res = tools.om_inspect({"blobId": bid})
    assert res["error"]["code"] == "OM-IO-006"


def test_input_blob_deleted_on_completion(http) -> None:
    store, _ = http
    bid = store.put_result(_blank_pdf(), PRINCIPAL)["blobId"]
    tools.om_read({"blobId": bid})
    assert tools.om_inspect({"blobId": bid})["error"]["code"] == "OM-IO-006"


def test_foreign_principal_blob_rejected(http) -> None:
    store, _ = http
    bid = store.put_result(_blank_pdf(), "ip:someone-else")["blobId"]
    res = tools.om_read({"blobId": bid})
    assert res["error"]["code"] == "OM-IO-007"


def test_rate_limit_returns_014(http) -> None:
    tools.set_rate_limiter(InMemoryRateLimiter(limit=1, window_seconds=60, now=Clock()))
    tools.om_validate(SAMPLE)  # 1st ok
    res = tools.om_validate(SAMPLE)  # 2nd exceeds
    assert res["error"]["code"] == "OM-IO-014"
    assert res["error"]["retryAfter"] > 0


# ---- principal middleware ----

def test_principal_middleware_sets_from_bearer_and_ip() -> None:
    from openom_mcp.principal import extract_principal

    captured: dict[str, str | None] = {}

    async def capture(scope, receive, send):  # noqa: ANN001 - inner ASGI app under test
        captured["p"] = tools._current_principal.get()

    async def call(headers, client):  # noqa: ANN001
        wrapped = server.principal_asgi(capture, extract_principal)
        scope = {"type": "http", "headers": headers, "client": client}
        await wrapped(scope, None, None)

    anyio.run(call, [(b"authorization", b"Bearer secret-xyz")], ("5.6.7.8", 1234))
    assert captured["p"] is not None and captured["p"].startswith("key:")
    anyio.run(call, [], ("5.6.7.8", 1234))
    assert captured["p"] == "ip:5.6.7.8"


def _embed_sample() -> bytes:
    from openom_core.embed import embed

    return embed(_blank_pdf(), SAMPLE, asserted_date=str(SAMPLE["assertedDate"]))


def _one_image_pdf() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, (200, 100, 50))
    page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=pix)
    out = doc.tobytes()
    doc.close()
    return out


def test_extract_images_returns_blob_urls_over_http(http, tmp_path: Path) -> None:
    """[Ma3] Over the hosted transport a remote agent has no server FS, so image entries must
    carry fetchable {blobId, presignedGet}, never a server-local `path`."""
    store, _clock = http
    slot = tools.om_request_upload()
    (store.root / slot["blobId"]).write_bytes(_one_image_pdf())  # simulate the client PUT
    res = tools.om_extract_images({"blobId": slot["blobId"]})
    imgs = res["manifest"]
    assert imgs, "expected at least one extracted image"
    for e in imgs:
        assert "path" not in e
        assert e["blobId"] and e["presignedGet"]


def test_extract_images_returns_local_path_over_stdio(tmp_path: Path) -> None:
    tools.set_resolver(PdfResolver(transport="stdio"))
    try:
        p = tmp_path / "img.pdf"
        p.write_bytes(_one_image_pdf())
        res = tools.om_extract_images({"path": str(p)}, out_dir=str(tmp_path / "out"))
        for e in res["manifest"]:
            assert "path" in e and "blobId" not in e
    finally:
        tools.set_resolver(None)
