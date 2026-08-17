"""M3 #46: LIVE SSRF path — exercise the real _default_opener/_default_resolver over a genuine TLS
socket, which the injected-opener unit tests in test_ssrf.py cannot cover. A self-signed cert +
threaded HTTPS loopback server prove: real TLS+read+%PDF sniff, connect-to-the-pinned-IP while
presenting the original Host (rebind defense), and real redirect following. The block-list is
patched to permit loopback ONLY here (range logic is proven in test_ssrf.py); this file targets the
socket code.
"""

from __future__ import annotations

import datetime
import http.server
import ipaddress
import ssl
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from openom_mcp import fetch
from openom_mcp.fetch import SafeFetcher, _default_resolver

PDF = b"%PDF-1.7\nlive\n%%EOF\n"
HOSTNAME = "pinned.test"


def _make_cert(tmp: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOSTNAME)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(HOSTNAME), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_pem = tmp / "cert.pem"
    key_pem = tmp / "key.pem"
    cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_pem.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_pem, key_pem


class _Handler(http.server.BaseHTTPRequestHandler):
    hosts_seen: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        _Handler.hosts_seen.append(self.headers.get("Host", ""))
        if self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/pdf")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")  # deliberately wrong; body sniff must win
        self.end_headers()
        self.wfile.write(PDF)

    def log_message(self, *args: object) -> None:  # silence
        pass


@pytest.fixture(scope="module")
def https_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[int, str]]:
    tmp = tmp_path_factory.mktemp("tls")
    cert_pem, key_pem = _make_cert(tmp)
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(cert_pem), keyfile=str(key_pem))
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], str(cert_pem)
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _allow_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Range logic is proven in test_ssrf.py; here we target the socket path, so permit loopback.
    monkeypatch.setattr(fetch, "_BLOCKED", [])


def test_default_resolver_resolves_localhost() -> None:
    ips = _default_resolver("localhost")
    assert ips and any(ip in ("127.0.0.1", "::1") for ip in ips)


def test_default_resolver_unknown_host_is_empty() -> None:
    assert _default_resolver("nonexistent.invalid.") == []


def test_live_https_fetch_over_real_tls(https_server: tuple[int, str]) -> None:
    port, ca = https_server
    _Handler.hosts_seen.clear()
    f = SafeFetcher(
        max_bytes=10_000, resolver=lambda h: ["127.0.0.1"],
        verify=ssl.create_default_context(cafile=ca),
    )
    body = f.get(f"https://{HOSTNAME}:{port}/pdf")
    assert body == PDF  # real TLS + read + %PDF sniff (Content-Type was image/png, ignored)
    # Pinning: connected to 127.0.0.1 yet presented the original Host, not the pinned IP.
    assert any(HOSTNAME in h for h in _Handler.hosts_seen)


def test_live_redirect_followed(https_server: tuple[int, str]) -> None:
    port, ca = https_server
    f = SafeFetcher(
        max_bytes=10_000, resolver=lambda h: ["127.0.0.1"],
        verify=ssl.create_default_context(cafile=ca),
    )
    assert f.get(f"https://{HOSTNAME}:{port}/redir") == PDF  # 302 -> /pdf, re-checked + fetched
