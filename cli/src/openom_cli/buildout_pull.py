# SPDX-License-Identifier: MIT
"""Pull a Buildout back-catalog into local files for ``om buildout-manifest`` (#B3).

Closes the acquisition gap: instead of hand-extracting one ``get_listing`` JSON per listing and
downloading every OM PDF by hand, this fetches them in one authenticated pass. Deterministic and
zero-inference (a data fetch). The pure orchestrator ``pull`` is transport-injected so it is fully
unit-testable with a fake; the real MCP Streamable-HTTP transport (``mcp_http_call_tool``) mirrors
the extension's ``buildout-http.ts`` (initialize -> initialized -> tools/call, JSON or SSE).

The real live endpoint run is environment-gated (a Buildout MCP endpoint + token), like the
extension's real-Prompt-API check - stated, not faked. The transport wire-format and SSE parser ARE
unit-tested here.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# (tool_name, arguments) -> the tool's result object (the listing dict).
CallTool = Callable[[str, dict[str, Any]], dict[str, Any]]
# url -> raw PDF bytes.
FetchBytes = Callable[[str], bytes]

_PDF_URL = re.compile(r"https?://\S+?\.pdf(?:\?\S*)?", re.IGNORECASE)


def om_url_of(listing: dict[str, Any]) -> str | None:
    """Best-effort find the OM PDF URL inside a listing object, else None.

    Checks the obvious explicit places, then falls back to the first ``…\\.pdf`` URL anywhere in the
    record. Never guesses a non-PDF link. A None result means "no OM PDF found" - the caller records
    it and moves on (the listing JSON is still written)."""
    for key in ("om_url", "offering_memorandum_url", "document_url"):
        v = listing.get(key)
        if isinstance(v, str) and v.lower().split("?")[0].endswith(".pdf"):
            return v
    docs = listing.get("documents")
    if isinstance(docs, list):
        for d in docs:
            url = d.get("url") if isinstance(d, dict) else None
            if isinstance(url, str) and url.lower().split("?")[0].endswith(".pdf"):
                return url
    m = _PDF_URL.search(json.dumps(listing))
    return m.group(0) if m else None


def ids_from_search_result(result: Any) -> list[str]:
    """Extract listing ids from a search tool result (best-effort over common shapes).

    Handles a bare list of ids, a list of listing objects (``id``/``listing_id``), or a wrapper
    ``{listings|results|data: [...]}``. Ids are stringified + de-duplicated, order preserved."""
    rows: Any = result
    if isinstance(result, dict):
        for key in ("listings", "results", "data", "items"):
            if isinstance(result.get(key), list):
                rows = result[key]
                break
    out: list[str] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        rid: Any = None
        if isinstance(row, str | int):
            rid = row
        elif isinstance(row, dict):
            rid = row.get("id") or row.get("listing_id") or row.get("ref")
        if rid is None:
            continue
        s = str(rid)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _pull_one(
    lid: str,
    *,
    get_listing: CallTool,
    fetch_pdf: FetchBytes,
    out_listings_dir: Path,
    out_pdf_dir: Path,
    listing_tool: str,
    om_url: Callable[[dict[str, Any]], str | None],
    skip_existing: bool,
) -> dict[str, str]:
    pdf_path = out_pdf_dir / f"{lid}.pdf"
    if skip_existing and pdf_path.exists() and (out_listings_dir / f"{lid}.json").exists():
        return {"id": lid, "status": "exists"}
    try:
        listing = get_listing(listing_tool, {"ref": lid})
    except Exception as e:  # noqa: BLE001 - report per-listing, keep going
        return {"id": lid, "status": "listing-error", "detail": str(e)}
    (out_listings_dir / f"{lid}.json").write_text(
        json.dumps(listing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    url = om_url(listing)
    if not url:
        return {"id": lid, "status": "no-om"}
    try:
        pdf_path.write_bytes(fetch_pdf(url))
        return {"id": lid, "status": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"id": lid, "status": "pdf-error", "detail": str(e)}


def pull(
    ids: list[str],
    *,
    get_listing: CallTool,
    fetch_pdf: FetchBytes,
    out_listings_dir: Path,
    out_pdf_dir: Path,
    listing_tool: str = "get_listing",
    om_url: Callable[[dict[str, Any]], str | None] = om_url_of,
    skip_existing: bool = False,
    jobs: int = 1,
) -> dict[str, Any]:
    """Fetch each listing id -> write ``<id>.json`` and download its OM PDF -> ``<id>.pdf``.

    Returns ``{pulled, of, counts, results}`` (results in input order). Pure except the injected
    effects (get_listing / fetch_pdf / filesystem), so it is deterministic + testable. A per-listing
    error is captured (never aborts the run); ``skip_existing`` avoids re-pulling already-downloaded
    OMs (resume); ``jobs>1`` downloads concurrently (I/O-bound) while keeping input order."""
    out_listings_dir.mkdir(parents=True, exist_ok=True)
    out_pdf_dir.mkdir(parents=True, exist_ok=True)

    def do(lid: str) -> dict[str, str]:
        return _pull_one(
            lid, get_listing=get_listing, fetch_pdf=fetch_pdf,
            out_listings_dir=out_listings_dir, out_pdf_dir=out_pdf_dir,
            listing_tool=listing_tool, om_url=om_url, skip_existing=skip_existing,
        )

    if jobs > 1 and len(ids) > 1:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(do, ids))  # ex.map preserves input order
    else:
        results = [do(lid) for lid in ids]

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    pulled = counts.get("ok", 0)
    return {"pulled": pulled, "of": len(ids), "counts": counts, "results": results}


# --- real MCP Streamable-HTTP transport (network; parser unit-tested, live call env-gated) ---
def parse_rpc(content_type: str, body: str) -> dict[str, Any]:
    """Parse an MCP HTTP response body that is application/json OR an SSE (text/event-stream)."""
    if "text/event-stream" in content_type:
        data = [
            ln[5:].strip()
            for ln in body.splitlines()
            if ln.startswith("data:") and ln[5:].strip()
        ]
        if not data:
            raise ValueError("empty SSE response")
        parsed: dict[str, Any] = json.loads(data[-1])
        return parsed
    body_parsed: dict[str, Any] = json.loads(body)
    return body_parsed


def listing_from_result(rpc: dict[str, Any]) -> dict[str, Any]:
    """Pull the listing out of a tools/call result (structuredContent, or a JSON text block)."""
    if "error" in rpc and rpc["error"]:
        err = rpc["error"]
        raise RuntimeError(f"Buildout MCP error {err.get('code')}: {err.get('message')}")
    result = rpc.get("result") or {}
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            text_parsed: dict[str, Any] = json.loads(block["text"])
            return text_parsed
    raise RuntimeError("Buildout MCP returned no listing content")


def mcp_http_call_tool(
    endpoint: str,
    token: str | None,
    tool: str,
    arguments: dict[str, Any],
    *,
    opener: Callable[[urllib.request.Request], Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """One tools/call over MCP Streamable HTTP: initialize -> initialized -> tools/call. Network."""

    def post(session_id: str | None, payload: dict[str, Any]) -> Any:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        req = urllib.request.Request(
            endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        return opener(req)

    init = post(
        None,
        {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "openom-cli", "version": "0.1"},
            },
        },
    )
    session_id = init.headers.get("mcp-session-id")
    post(session_id, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    resp = post(
        session_id,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": tool, "arguments": arguments}},
    )
    body = resp.read().decode()
    return listing_from_result(parse_rpc(resp.headers.get("content-type") or "", body))


def http_fetch_pdf(url: str, *, opener: Callable[[str], Any] = urllib.request.urlopen) -> bytes:
    """Download PDF bytes from an https URL (network)."""
    with opener(url) as r:
        data: bytes = r.read()
        return data
