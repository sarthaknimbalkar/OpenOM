# SPDX-License-Identifier: MIT
"""FastMCP server exposing the openOM tool surface (spec §I) over stdio (M1).

Thin wrapper: each tool delegates to the pure, deterministic bodies in ``tools.py``. Remote
(Streamable HTTP) transport + url/blobId inputs + SSRF are M3. Zero inference, zero network
(the cardinal boundary; §V [OM-MCP-007]).
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from . import tools

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


def main() -> None:  # pragma: no cover — blocking stdio loop, exercised out-of-process
    """Entry point (`om-mcp`): run the server over stdio."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
