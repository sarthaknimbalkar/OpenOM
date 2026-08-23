"""Unit-cover the real MCP Streamable-HTTP transport helpers with an injected opener (no network):
parse_rpc (json + SSE), listing_from_result (all branches), mcp_http_call_tool, http_fetch_pdf."""

from __future__ import annotations

import json

import pytest

from openom_cli.buildout_pull import (
    http_fetch_pdf,
    listing_from_result,
    mcp_http_call_tool,
    parse_rpc,
)


def test_parse_rpc_json() -> None:
    assert parse_rpc("application/json", '{"a": 1}') == {"a": 1}


def test_parse_rpc_sse_takes_last_data_line() -> None:
    body = 'event: message\ndata: {"n": 1}\n\ndata: {"n": 2}\n'
    assert parse_rpc("text/event-stream", body) == {"n": 2}


def test_parse_rpc_sse_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_rpc("text/event-stream", "event: ping\n\n")


def test_listing_from_result_structured_content() -> None:
    rpc = {"result": {"structuredContent": {"id": 7, "name": "X"}}}
    assert listing_from_result(rpc)["id"] == 7


def test_listing_from_result_text_block() -> None:
    rpc = {"result": {"content": [{"type": "text", "text": json.dumps({"id": 9})}]}}
    assert listing_from_result(rpc)["id"] == 9


def test_listing_from_result_error_raises() -> None:
    with pytest.raises(RuntimeError, match="Buildout MCP error"):
        listing_from_result({"error": {"code": -32000, "message": "nope"}})


def test_listing_from_result_no_content_raises() -> None:
    with pytest.raises(RuntimeError, match="no listing content"):
        listing_from_result({"result": {"content": []}})


class _Resp:
    def __init__(self, body: str, ctype: str = "application/json", sid: str | None = None) -> None:
        self._body = body
        self.headers = {"content-type": ctype, "mcp-session-id": sid}

    def read(self) -> bytes:
        return self._body.encode()

    # http_fetch_pdf uses the response as a context manager
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None


def test_mcp_http_call_tool_full_handshake() -> None:
    calls: list[dict] = []

    def opener(req):  # noqa: ANN001 - urllib.request.Request
        payload = json.loads(req.data.decode())
        calls.append(payload)
        if payload.get("method") == "initialize":
            return _Resp("{}", sid="sess-1")
        if payload.get("method") == "tools/call":
            return _Resp(json.dumps({"result": {"structuredContent": {"id": 42}}}))
        return _Resp("{}")

    out = mcp_http_call_tool(
        "https://mcp.example.com/mcp", "tok", "get_listing", {"id": 42}, opener=opener
    )
    assert out["id"] == 42
    methods = [c.get("method") for c in calls]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]


def test_http_fetch_pdf() -> None:
    def opener(url):  # noqa: ANN001
        assert url.startswith("https://")
        return _Resp("%PDF-1.7 body")

    assert http_fetch_pdf("https://cdn.example.com/x.pdf", opener=opener) == b"%PDF-1.7 body"
