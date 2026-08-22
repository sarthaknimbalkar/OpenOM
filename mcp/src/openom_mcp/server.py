# SPDX-License-Identifier: MIT
"""FastMCP server exposing the openOM tool surface (spec §I) over stdio (M1).

Thin wrapper: each tool delegates to the pure, deterministic bodies in ``tools.py``. Remote
(Streamable HTTP) transport + url/blobId inputs + SSRF are M3. Zero inference, zero network
(the cardinal boundary; §V [OM-MCP-007]).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from . import tools
from .blobstore import BlobStore, LocalBlobStore

mcp = MCPServer("openom")


@mcp.tool()
def om_inspect(pdf: dict[str, Any], verifyOrigin: bool = False) -> dict[str, Any]:
    """Classify a PDF (native/hybrid/scanned) and report the payload/image/text profile."""
    return tools.om_inspect(pdf, verify_origin=verifyOrigin)


@mcp.tool()
def om_read(pdf: dict[str, Any], verifyOrigin: bool = True) -> dict[str, Any]:
    """Read + integrity-verify the embedded om.json payload (the cheap consumer path)."""
    return tools.om_read(pdf, verify_origin=verifyOrigin)


@mcp.tool()
def om_extract_text(
    pdf: dict[str, Any],
    pageRange: str | None = None,
    cursor: str | None = None,
    maxChars: int = 100_000,
) -> dict[str, Any]:
    """Paginated text + best-effort tables for a page range."""
    return tools.om_extract_text(pdf, page_range=pageRange, cursor=cursor, max_chars=maxChars)


@mcp.tool()
def om_extract_images(
    pdf: dict[str, Any],
    outDir: str | None = None,
    pageRange: str | None = None,
    includeVector: bool = False,
) -> dict[str, Any]:
    """Image manifest + local paths (SMask→RGBA, CMYK→sRGB, xref+content dedupe); never bytes."""
    return tools.om_extract_images(
        pdf, out_dir=outDir, page_range=pageRange, include_vector=includeVector
    )


@mcp.tool()
def om_validate(
    payload: dict[str, Any], tolerances: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Two-tier validation report (schema errors block; consistency warnings never block)."""
    return tools.om_validate(payload, tolerances=tolerances)


@mcp.tool()
def om_embed(
    pdf: dict[str, Any],
    payload: dict[str, Any],
    outPath: str | None = None,
    badge: bool = False,
    sourceDocHash: bool = False,
) -> dict[str, Any]:
    """Validate-then-embed om.json into a NEW PDF; refuse on schema errors, warnings pass."""
    return tools.om_embed(
        pdf, payload, out_path=outPath, badge=badge, source_doc_hash=sourceDocHash
    )


@mcp.tool()
def om_request_upload() -> dict[str, Any]:
    """Hosted-only: reserve a single-use presigned upload target; returns {blobId, presignedPut}."""
    return tools.om_request_upload()


def build_http_app(
    *,
    max_fetch_bytes: int = 200 * 1024 * 1024,
    rate_limit: int = 120,
    rate_window_seconds: int = 60,
    blob_root: Path | None = None,
    blob_store: BlobStore | None = None,
    rate_limiter: Any = None,
    dns_rebinding_protection: bool = False,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> Any:
    """Wire the deterministic hosted transport and return the Streamable HTTP ASGI app (M3).

    Injects the http ``PdfResolver`` (SafeFetcher + BlobStore), the rate limiter, and a principal
    middleware that sets ``tools._current_principal`` from ``Authorization``/client IP per request.
    Zero inference - the paid extraction service is a separate deployment ([OM-DoD-008]).

    HTTP-layer transport security (#48): pass ``dns_rebinding_protection=True`` with
    ``allowed_hosts``/``allowed_origins`` for a public deployment (rejects spoofed Host/Origin,
    the browser-DNS-rebinding defense). Off by default so self-hosting on localhost is friction-free
    - this is inbound protection and is orthogonal to the outbound SSRF ruleset in ``fetch.py``.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    from .fetch import SafeFetcher
    from .principal import extract_principal
    from .ratelimit import InMemoryRateLimiter
    from .resolve import PdfResolver

    root = blob_root or Path(tempfile.mkdtemp(prefix="openom-blobs-"))
    store = blob_store or LocalBlobStore(root)
    fetcher = SafeFetcher(max_bytes=max_fetch_bytes)
    tools.set_resolver(PdfResolver(transport="http", fetcher=fetcher, blobstore=store))
    tools.set_rate_limiter(
        rate_limiter
        if rate_limiter is not None
        else InMemoryRateLimiter(limit=rate_limit, window_seconds=rate_window_seconds)
    )

    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=dns_rebinding_protection,
        allowed_hosts=allowed_hosts or [],
        allowed_origins=allowed_origins or [],
    )
    return principal_asgi(mcp.streamable_http_app(transport_security=security), extract_principal)


def principal_asgi(app: Any, extract: Any) -> Any:
    """Wrap an ASGI ``app`` so each HTTP request sets ``tools._current_principal`` from its headers/
    client IP (``extract(headers, client_ip)``), reset afterwards. Non-http scopes pass through."""

    import logging
    import time

    from .log import event

    async def middleware(scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        client_ip = (scope.get("client") or ("unknown",))[0]
        principal = extract(headers, client_ip)
        token = tools._current_principal.set(principal)
        # Per-request observability (#152): principal + path + status + duration, no request bodies.
        status = {"code": 0}

        async def _send(message: Any) -> None:
            if message.get("type") == "http.response.start":
                status["code"] = message.get("status", 0)
            await send(message)

        start = time.monotonic()
        try:
            await app(scope, receive, _send)
        finally:
            tools._current_principal.reset(token)
            event(
                logging.INFO,
                "request",
                principal=principal,
                method=scope.get("method"),
                path=scope.get("path"),
                status=status["code"],
                ms=round((time.monotonic() - start) * 1000, 1),
            )

    return middleware


def main() -> None:  # pragma: no cover - blocking stdio loop, exercised out-of-process
    """Entry point (`om-mcp`): run the server over stdio."""
    mcp.run("stdio")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def http_config_from_env() -> tuple[str, int, dict[str, Any]]:
    """Resolve `om-mcp-http` config from the environment ([Ma7]).

    Safe by default: binds loopback (127.0.0.1) so `pip install openom-mcp && om-mcp-http` is not a
    world-open server. When bound to a non-loopback host, DNS-rebinding protection defaults ON (set
    OPENOM_MCP_ALLOWED_HOSTS/ORIGINS accordingly). Every knob is overridable:

      OPENOM_MCP_HOST (default 127.0.0.1) · OPENOM_MCP_PORT (8080)
      OPENOM_MCP_MAX_FETCH_BYTES (209715200)
      OPENOM_MCP_RATE_LIMIT (120) · OPENOM_MCP_RATE_WINDOW (60)
      OPENOM_MCP_MAX_PAGES (0 = unset) · OPENOM_MCP_DNS_REBINDING (auto)
      OPENOM_MCP_ALLOWED_HOSTS / OPENOM_MCP_ALLOWED_ORIGINS (comma-separated)

    Production R2/Redis/api-key backends stay reachable by importing build_http_app() directly.
    """
    host = os.environ.get("OPENOM_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _env_int("OPENOM_MCP_PORT", 8080)
    is_loopback = host in {"127.0.0.1", "::1", "localhost"}
    dns_override = _env_bool("OPENOM_MCP_DNS_REBINDING")
    dns_rebinding = dns_override if dns_override is not None else not is_loopback
    kwargs: dict[str, Any] = {
        "max_fetch_bytes": _env_int("OPENOM_MCP_MAX_FETCH_BYTES", 200 * 1024 * 1024),
        "rate_limit": _env_int("OPENOM_MCP_RATE_LIMIT", 120),
        "rate_window_seconds": _env_int("OPENOM_MCP_RATE_WINDOW", 60),
        "dns_rebinding_protection": dns_rebinding,
        "allowed_hosts": _env_list("OPENOM_MCP_ALLOWED_HOSTS"),
        "allowed_origins": _env_list("OPENOM_MCP_ALLOWED_ORIGINS"),
    }
    return host, port, kwargs


def backends_from_env(rate_limit: int, rate_window_seconds: int) -> dict[str, Any]:
    """Select production blob/limiter backends from the environment ([Ma7]).

      OPENOM_MCP_BLOB_BACKEND = local (default) | r2
        r2 needs: OPENOM_R2_BUCKET, OPENOM_R2_ENDPOINT, OPENOM_R2_ACCESS_KEY, OPENOM_R2_SECRET_KEY
      OPENOM_MCP_LIMITER = memory (default) | redis
        redis needs: OPENOM_REDIS_URL (a redis-py-compatible client is imported lazily)

    Returns kwargs for build_http_app (blob_store / rate_limiter), empty when defaults apply.
    """
    out: dict[str, Any] = {}
    if os.environ.get("OPENOM_MCP_BLOB_BACKEND", "local").strip().lower() == "r2":
        from .blobstore import S3BlobStore

        bucket = os.environ.get("OPENOM_R2_BUCKET", "").strip()
        if not bucket:
            raise SystemExit("OPENOM_MCP_BLOB_BACKEND=r2 requires OPENOM_R2_BUCKET")
        out["blob_store"] = S3BlobStore(
            bucket=bucket,
            endpoint_url=os.environ.get("OPENOM_R2_ENDPOINT", ""),
            access_key=os.environ.get("OPENOM_R2_ACCESS_KEY", ""),
            secret_key=os.environ.get("OPENOM_R2_SECRET_KEY", ""),
        )
    if os.environ.get("OPENOM_MCP_LIMITER", "memory").strip().lower() == "redis":
        from .ratelimit import DistributedRateLimiter
        from .redisstore import RedisCounterStore

        url = os.environ.get("OPENOM_REDIS_URL", "").strip()
        if not url:
            raise SystemExit("OPENOM_MCP_LIMITER=redis requires OPENOM_REDIS_URL")
        import redis  # lazy: not a hard dep

        store = RedisCounterStore(redis.from_url(url))
        out["rate_limiter"] = DistributedRateLimiter(
            store, limit=rate_limit, window_seconds=rate_window_seconds
        )
    return out


def main_http() -> None:  # pragma: no cover - blocking server loop, exercised out-of-process
    """Entry point (`om-mcp-http`): run the deterministic Streamable HTTP server (M3).

    Config comes from the environment (see http_config_from_env) with a SAFE default: loopback bind,
    DNS-rebinding protection auto-on when bound publicly.
    """
    import logging

    import uvicorn

    from .log import event

    host, port, kwargs = http_config_from_env()
    kwargs.update(backends_from_env(kwargs["rate_limit"], kwargs["rate_window_seconds"]))
    max_pages = _env_int("OPENOM_MCP_MAX_PAGES", 0)
    if max_pages > 0:
        tools.set_max_pages(max_pages)
    if host not in {"127.0.0.1", "::1", "localhost"} and not kwargs["allowed_hosts"]:
        event(
            logging.WARNING,
            "http_public_bind_without_allowed_hosts",
            host=host,
            hint="set OPENOM_MCP_ALLOWED_HOSTS/ORIGINS for the DNS-rebinding defense",
        )
    event(
        logging.INFO,
        "http_start",
        host=host,
        port=port,
        dns_rebinding=kwargs["dns_rebinding_protection"],
    )
    uvicorn.run(build_http_app(**kwargs), host=host, port=port)


if __name__ == "__main__":
    main()
