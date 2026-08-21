"""M3 Task 1: SSRF-hardened safe_fetch ([OM-SEC-001/011/014]). Every rule is exercised offline -
the DNS resolver and the connection opener are both injected, so range logic, redirect re-checking,
resolve-then-pin, timeouts, size caps, and the %PDF- sniff are tested without any real network.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from openom_mcp.fetch import SafeFetcher, is_blocked
from openom_mcp.tools import ToolError

PDF = b"%PDF-1.7\n%%EOF\n"


class FakeResponse:
    def __init__(self, status: int, body: bytes = b"", headers: Mapping[str, str] | None = None):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self._body = body

    def iter_bytes(self, chunk: int = 4) -> Iterator[bytes]:
        for i in range(0, len(self._body), chunk):
            yield self._body[i : i + chunk]

    def close(self) -> None:  # noqa: D401 - protocol shim
        pass


def _resolver(mapping: dict[str, list[str]]):
    return lambda host: mapping.get(host, [])


def _opener(responses: list[object]):
    """Pop a queued response per hop; records the pinned IP each call for pinning assertions."""
    calls: list[str] = []

    def open_pinned(pinned_ip: str, host: str, url: str, **_: object) -> object:
        calls.append(pinned_ip)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    open_pinned.calls = calls  # type: ignore[attr-defined]
    return open_pinned


def _fetch(url, *, resolver, responses, max_bytes=10_000, **kw):
    opener = _opener(list(responses))
    f = SafeFetcher(max_bytes=max_bytes, resolver=resolver, opener=opener, **kw)
    return f, opener


def test_non_https_scheme_rejected() -> None:
    f, _ = _fetch("x", resolver=_resolver({}), responses=[])
    for bad in ("http://h/x", "file:///etc/passwd", "data:application/pdf;base64,AA", "ftp://h/x"):
        with pytest.raises(ToolError) as e:
            f.get(bad)
        assert e.value.code == "OM-IO-008"


@pytest.mark.parametrize(
    "ip",
    ["10.0.0.1", "172.16.0.1", "192.168.1.1", "127.0.0.1", "169.254.169.254",
     "100.64.0.1", "::1", "fc00::1"],
)
def test_each_blocked_range_rejected(ip: str) -> None:
    f, _ = _fetch("https://evil/x", resolver=_resolver({"evil": [ip]}), responses=[])
    with pytest.raises(ToolError) as e:
        f.get("https://evil/x")
    assert e.value.code == "OM-IO-002"


def test_is_blocked_matrix() -> None:
    assert is_blocked("10.1.2.3") and is_blocked("169.254.169.254") and is_blocked("::1")
    assert not is_blocked("8.8.8.8") and not is_blocked("1.1.1.1")


def test_public_ip_pdf_returns_bytes() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[FakeResponse(200, PDF, {"content-type": "text/plain"})],
    )
    assert f.get("https://ok/x") == PDF


def test_content_type_ignored_body_sniffed() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[FakeResponse(200, PDF, {"content-type": "image/png"})],
    )
    assert f.get("https://ok/x") == PDF


def test_non_pdf_body_rejected_005() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[FakeResponse(200, b"<html>not a pdf</html>")],
    )
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-005"


def test_oversize_body_capped_005() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[FakeResponse(200, PDF + b"A" * 5000)], max_bytes=100,
    )
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-005"


def test_cross_range_redirect_refused_002() -> None:
    resolver = _resolver({"ok": ["93.184.216.34"], "internal": ["169.254.169.254"]})
    f, _ = _fetch(
        "https://ok/x", resolver=resolver,
        responses=[FakeResponse(302, headers={"location": "https://internal/meta"})],
    )
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-002"  # the redirected host resolves to a blocked range


def test_redirect_limit_exceeded_009() -> None:
    resolver = _resolver({"ok": ["93.184.216.34"]})
    hops = [FakeResponse(302, headers={"location": "https://ok/next"}) for _ in range(7)]
    f, _ = _fetch("https://ok/x", resolver=resolver, responses=hops, max_redirects=5)
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-009"


def test_timeout_maps_to_003() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[TimeoutError("read stalled")],
    )
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-003"


def test_connect_failure_maps_to_001() -> None:
    f, _ = _fetch(
        "https://ok/x", resolver=_resolver({"ok": ["93.184.216.34"]}),
        responses=[ConnectionError("refused")],
    )
    with pytest.raises(ToolError) as e:
        f.get("https://ok/x")
    assert e.value.code == "OM-IO-001"


def test_dns_failure_maps_to_001() -> None:
    f, _ = _fetch("https://nope/x", resolver=_resolver({}), responses=[])
    with pytest.raises(ToolError) as e:
        f.get("https://nope/x")
    assert e.value.code == "OM-IO-001"


def test_resolve_then_pin_uses_validated_ip() -> None:
    # A rebind: first resolve returns a public IP (validated + pinned); a naive re-resolve would
    # return a blocked IP. The fetcher MUST connect to the pinned public IP and NOT re-resolve.
    seq = [["93.184.216.34"], ["169.254.169.254"]]

    def rebinding(host: str) -> list[str]:
        return seq.pop(0) if seq else ["169.254.169.254"]

    opener = _opener([FakeResponse(200, PDF)])
    f = SafeFetcher(max_bytes=10_000, resolver=rebinding, opener=opener)
    assert f.get("https://ok/x") == PDF
    assert opener.calls == ["93.184.216.34"]  # connected to the pinned validated IP, once
