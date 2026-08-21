"""M3 #48: HTTP-layer transport security. With DNS-rebinding protection enabled + an allowed-hosts
list, a spoofed Host is rejected (421) and a disallowed Origin is rejected (403) BEFORE reaching
the MCP handler - the browser-DNS-rebinding defense. Off by default (self-host), so this configures
it explicitly. Orthogonal to the outbound SSRF ruleset (fetch.py).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from openom_mcp import server, tools


@pytest.fixture
def secured_base(tmp_path) -> Iterator[str]:
    app = server.build_http_app(
        blob_root=tmp_path,
        dns_rebinding_protection=True,
        allowed_hosts=["good.host", "good.host:*"],
        allowed_origins=["https://good.host"],
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", lifespan="on")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert srv.started
    port = srv.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        srv.should_exit = True
        thread.join(timeout=10)
        tools.set_resolver(None)
        tools.set_rate_limiter(None)


def _post(url: str, headers: dict[str, str]) -> httpx.Response:
    base = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    body = '{"jsonrpc":"2.0","id":1,"method":"ping"}'
    return httpx.post(url, headers={**base, **headers}, content=body, timeout=10)


def test_spoofed_host_rejected_421(secured_base: str) -> None:
    r = _post(secured_base, {"Host": "evil.example"})
    assert r.status_code == 421  # Invalid Host header - blocked before the MCP handler


def test_disallowed_origin_rejected_403(secured_base: str) -> None:
    r = _post(secured_base, {"Host": "good.host", "Origin": "https://evil.example"})
    assert r.status_code == 403  # Invalid Origin header


def test_allowed_host_passes_security(secured_base: str) -> None:
    r = _post(secured_base, {"Host": "good.host", "Origin": "https://good.host"})
    assert r.status_code not in (421, 403)  # got past security into the MCP layer
