"""M3 #47: TRUE HTTP round-trip over a real socket. Runs the Streamable HTTP app under uvicorn in a
thread (so the session-manager lifespan actually starts) and drives it with the MCP client over
real HTTP - exercising the principal middleware + SDK framing end-to-end. Proves the surface is
served over HTTP and that a principal from a real Authorization header reaches the tool layer.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import anyio
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from openom_mcp import server, tools
from openom_mcp.principal import extract_principal

SPEC = Path(__file__).resolve().parents[2] / "spec"
SAMPLE = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


@pytest.fixture
def http_base(tmp_path: Path) -> Iterator[tuple[str, object]]:
    app = server.build_http_app(blob_root=tmp_path)
    store = tools._resolver().blobstore
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert srv.started, "uvicorn did not start"
    port = srv.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/mcp", store
    finally:
        srv.should_exit = True
        thread.join(timeout=10)
        tools.set_resolver(None)
        tools.set_rate_limiter(None)


async def _call(url: str, headers: dict[str, str], tool: str, args: dict) -> tuple[list[str], dict]:
    import httpx2

    client = httpx2.AsyncClient(headers=headers)
    async with streamable_http_client(url, http_client=client) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            res = await session.call_tool(tool, args)
            return names, json.loads(res.content[0].text)  # type: ignore[union-attr]


def test_real_http_serves_surface_and_validates(http_base: tuple[str, object]) -> None:
    url, _ = http_base
    names, out = anyio.run(_call, url, {}, "om_validate", {"payload": SAMPLE})
    assert "om_request_upload" in names and len(names) == 7
    assert out["ok"] is True


def test_principal_from_http_header_reaches_tool(http_base: tuple[str, object]) -> None:
    url, store = http_base
    _, out = anyio.run(
        _call, url, {"Authorization": "Bearer secret-key-xyz"}, "om_request_upload", {}
    )
    owner = store._meta[out["blobId"]]["owner"]  # type: ignore[union-attr]
    assert owner == extract_principal({"authorization": "Bearer secret-key-xyz"}, "x")
    assert str(owner).startswith("key:")  # header -> middleware -> tool proven over real HTTP
