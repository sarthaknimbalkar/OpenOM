# SPDX-License-Identifier: MIT
"""FastMCP server exposing the openOM tool surface (spec §I) over stdio (M1).

Thin wrapper: each tool delegates to the pure, deterministic bodies in ``tools.py``. Remote
(Streamable HTTP) transport + url/blobId inputs + SSRF are M3. Zero inference, zero network
(the cardinal boundary; §V [OM-MCP-007]).
"""

from __future__ import annotations

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
) -> Any:
    """Wire the deterministic hosted transport and return the Streamable HTTP ASGI app (M3).

    Injects the http ``PdfResolver`` (SafeFetcher + BlobStore), the rate limiter, and a principal
    middleware that sets ``tools._current_principal`` from ``Authorization``/client IP per request.
    Zero inference — the paid extraction service is a separate deployment ([OM-DoD-008]).
    """
    from .fetch import SafeFetcher
    from .principal import extract_principal
    from .ratelimit import InMemoryRateLimiter
    from .resolve import PdfResolver

    root = blob_root or Path(tempfile.mkdtemp(prefix="openom-blobs-"))
    store = blob_store or LocalBlobStore(root)
    fetcher = SafeFetcher(max_bytes=max_fetch_bytes)
    tools.set_resolver(PdfResolver(transport="http", fetcher=fetcher, blobstore=store))
    tools.set_rate_limiter(
        InMemoryRateLimiter(limit=rate_limit, window_seconds=rate_window_seconds)
    )

    return principal_asgi(mcp.streamable_http_app(), extract_principal)


def principal_asgi(app: Any, extract: Any) -> Any:
    """Wrap an ASGI ``app`` so each HTTP request sets ``tools._current_principal`` from its headers/
    client IP (``extract(headers, client_ip)``), reset afterwards. Non-http scopes pass through."""

    async def middleware(scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        client_ip = (scope.get("client") or ("unknown",))[0]
        token = tools._current_principal.set(extract(headers, client_ip))
        try:
            await app(scope, receive, send)
        finally:
            tools._current_principal.reset(token)

    return middleware


def main() -> None:  # pragma: no cover — blocking stdio loop, exercised out-of-process
    """Entry point (`om-mcp`): run the server over stdio."""
    mcp.run("stdio")


def main_http() -> None:  # pragma: no cover — blocking server loop, exercised out-of-process
    """Entry point (`om-mcp-http`): run the deterministic Streamable HTTP server (M3)."""
    import uvicorn  # type: ignore[import-not-found]

    uvicorn.run(build_http_app(), host="0.0.0.0", port=8080)  # noqa: S104 - hosted service


if __name__ == "__main__":
    main()
