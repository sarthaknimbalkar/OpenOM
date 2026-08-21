# SPDX-License-Identifier: MIT
"""SSRF-hardened HTTPS fetch for ``url`` PdfRefs on the hosted transport ([OM-SEC-001/011/014]).

The fetcher is deterministic and fully injectable: the DNS ``resolver`` (host -> IPs) and the
connection ``opener`` (pinned-IP connect) are constructor parameters, so the range/redirect/pin
logic is tested offline. The default opener uses httpx and connects to the *pinned validated IP*
(resolve-then-pin) to mitigate DNS rebinding - no re-resolution between the block-list check and
the connection.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Protocol, cast
from urllib.parse import urljoin, urlparse

from .tools import ToolError

# Blocked address ranges ([OM-SEC-001]) - private, loopback, link-local (incl. cloud metadata
# 169.254.169.254), CGNAT, and IPv6 ULA/loopback. Verbatim from the spec.
_BLOCKED = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
        "169.254.0.0/16", "100.64.0.0/10", "::1/128", "fc00::/7",
    )
]
_REDIRECT_STATUS = {301, 302, 303, 307, 308}


def is_blocked(ip: str) -> bool:
    """True if ``ip`` falls in any blocked range ([OM-SEC-001])."""
    addr = ipaddress.ip_address(ip)
    return any(addr in net for net in _BLOCKED)


class FetchResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]

    def iter_bytes(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


Resolver = Callable[[str], list[str]]
Opener = Callable[..., FetchResponse]


def _default_resolver(host: str) -> list[str]:
    import socket

    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    return [str(info[4][0]) for info in infos]


def _default_opener(
    pinned_ip: str, host: str, url: str, *, connect_timeout: float, read_timeout: float,
    verify: Any = True,
) -> FetchResponse:
    import httpx

    # Connect to the pinned IP while presenting the original host for SNI + Host, so no
    # re-resolution happens between the block-list check and the socket connect (rebind defense).
    parsed = urlparse(url)
    netloc = pinned_ip if parsed.port is None else f"{pinned_ip}:{parsed.port}"
    target = parsed._replace(netloc=netloc).geturl()
    client = httpx.Client(
        follow_redirects=False,
        timeout=httpx.Timeout(
            connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout
        ),
        headers={"Host": host},
        verify=verify,
    )
    try:
        request = client.build_request("GET", target, extensions={"sni_hostname": host})
        resp = client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        client.close()
        raise TimeoutError(str(exc)) from exc
    except httpx.HTTPError as exc:
        client.close()
        raise ConnectionError(str(exc)) from exc
    return cast(FetchResponse, resp)  # caller reads iter_bytes() then close()


class SafeFetcher:
    """Fetch a PDF over HTTPS with the full SSRF ruleset; ``get`` returns bytes or raises."""

    def __init__(
        self,
        *,
        max_bytes: int,
        resolver: Resolver = _default_resolver,
        opener: Opener = _default_opener,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        max_redirects: int = 5,
        verify: Any = True,
    ) -> None:
        self.max_bytes = max_bytes
        self.resolver = resolver
        self.opener = opener
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_redirects = max_redirects
        self.verify = verify

    def get(self, url: str) -> bytes:
        for _hop in range(self.max_redirects + 1):
            parsed = urlparse(url)
            if parsed.scheme != "https":
                raise ToolError("OM-IO-008", f"only https URLs are fetched, got {parsed.scheme!r}")
            host = parsed.hostname or ""
            ips = self.resolver(host)
            if not ips:
                raise ToolError("OM-IO-001", f"DNS resolution failed for {host!r}", retryable=True)
            if any(is_blocked(ip) for ip in ips):
                raise ToolError("OM-IO-002", f"{host!r} resolves to a blocked address range")
            pinned = next(ip for ip in ips if not is_blocked(ip))
            resp = self._open(pinned, host, url)
            try:
                if resp.status_code in _REDIRECT_STATUS and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue  # next hop re-checks scheme + range
                return self._read_pdf(resp)
            finally:
                resp.close()
        raise ToolError("OM-IO-009", f"redirect limit ({self.max_redirects}) exceeded")

    def _open(self, pinned: str, host: str, url: str) -> FetchResponse:
        try:
            return self.opener(
                pinned, host, url,
                connect_timeout=self.connect_timeout, read_timeout=self.read_timeout,
                verify=self.verify,
            )
        except TimeoutError as exc:
            raise ToolError("OM-IO-003", f"fetch timeout: {exc}", retryable=True) from exc
        except (ConnectionError, OSError) as exc:
            raise ToolError("OM-IO-001", f"upstream fetch failed: {exc}", retryable=True) from exc

    def _read_pdf(self, resp: FetchResponse) -> bytes:
        buf = bytearray()
        for chunk in resp.iter_bytes():
            buf += chunk
            if len(buf) > self.max_bytes:
                raise ToolError("OM-IO-005", f"fetched body exceeds {self.max_bytes} bytes")
        if not bytes(buf).startswith(b"%PDF-"):
            raise ToolError("OM-IO-005", "fetched content is not a PDF (missing %PDF- header)")
        return bytes(buf)
