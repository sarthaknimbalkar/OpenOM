# SPDX-License-Identifier: MIT
"""openOM MCP tool implementations (spec §I) — pure, deterministic, inference-free.

These are the transport-independent tool bodies; ``server.py`` wires them to the MCP server
(stdio for M1). Each tool takes a ``PdfRef`` ({"path": ...} on stdio) and returns the §I.2
success shape or
the §I OM-MCP-004 error envelope ``{"error": {code, message, retryable, details?}}``.

M1/stdio accepts ``path`` only; ``url``/``blobId`` need the hosted transport (M3) → OM-IO-008.
No network, no inference (the cardinal boundary; §V, [OM-MCP-007]).
"""

from __future__ import annotations

import contextvars
import dataclasses
import tempfile
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .resolve import PdfResolver

import pikepdf
from openom_core.canonical import payload_hash
from openom_core.embed import embed as _embed
from openom_core.embed import read as _read
from openom_core.errors import CanonicalizationError, PayloadTooLargeError
from openom_core.images import extract_images as _extract_images
from openom_core.inspect import inspect as _inspect
from openom_core.schema import load_schema as _load_schema  # cached + wheel-safe (#148/#149)
from openom_core.text import CursorError, PageRangeError
from openom_core.text import extract_text as _extract_text
from openom_core.validate import Tolerances
from openom_core.validate import validate as _validate
from openom_core.xmp import read_marker


class ToolError(Exception):
    """A mapped tool failure carrying the §I error envelope fields."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after
        self.details = details


def _envelope(exc: ToolError) -> dict[str, Any]:
    err: dict[str, Any] = {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
    if exc.retry_after is not None:
        err["retryAfter"] = exc.retry_after
    if exc.details is not None:
        err["details"] = exc.details
    return {"error": err}


def _guard(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Map expected failures to the error envelope; never raise out of a tool (OM-MCP-004).

    Also enforces blob delete-on-completion (§K): any input blob consumed via ``_load_pdf`` during
    the call is deleted in ``finally`` (success or failure), never lingering past the request.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        token = _consumed_blobs.set([])
        try:
            if _LIMITER is not None:
                _LIMITER.check(_current_principal.get() or "")
            return fn(*args, **kwargs)
        except ToolError as exc:
            _log_failure(fn, exc.code)  # #152 — observe rate-limit/SSRF/IO rejections (hosted only)
            return _envelope(exc)
        except PayloadTooLargeError as exc:
            return _envelope(ToolError("OM-IO-BOMB", str(exc)))
        except PageRangeError as exc:
            return _envelope(ToolError("OM-IO-012", str(exc)))
        except CursorError as exc:
            return _envelope(ToolError("OM-IO-013", str(exc)))
        except CanonicalizationError as exc:
            return _envelope(ToolError(exc.code, str(exc)))
        except pikepdf.PdfError as exc:
            return _envelope(ToolError("OM-IO-010", f"malformed PDF: {exc}"))
        finally:
            _delete_consumed_blobs()
            _consumed_blobs.reset(token)

    return wrapper


def _log_failure(fn: Callable[..., Any], code: str) -> None:
    """Observe a mapped tool rejection on the HOSTED transport (#152). No-op on stdio (trusted-
    local); never logs request content — just the tool name, error code, and principal."""
    if _RESOLVER is None or _RESOLVER.transport != "http":
        return
    import logging

    from .log import event

    event(
        logging.WARNING, "tool_error", tool=getattr(fn, "__name__", "?"),
        code=code, principal=_current_principal.get(),
    )


def _delete_consumed_blobs() -> None:
    blobstore = getattr(_resolver(), "blobstore", None)
    if blobstore is not None:
        for blob_id in _consumed_blobs.get() or []:
            blobstore.delete(blob_id)


# The active PDF resolver + calling principal. Defaults to a stdio resolver so direct/stdio use and
# existing tests need no wiring; server.py's http entry injects an http resolver via set_resolver().
_RESOLVER: PdfResolver | None = None
_LIMITER: Any = None
_current_principal: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "openom_principal", default=None
)
# Input blobs consumed during the current tool call; deleted on completion by _guard.
_consumed_blobs: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "openom_consumed_blobs", default=None
)


def set_resolver(resolver: PdfResolver | None) -> None:
    """Install the active PdfResolver (http wires this; None restores the stdio default)."""
    global _RESOLVER
    _RESOLVER = resolver


def set_rate_limiter(limiter: Any) -> None:
    """Install the per-principal rate limiter (http wires this; None disables — stdio default)."""
    global _LIMITER
    _LIMITER = limiter


def _resolver() -> PdfResolver:
    global _RESOLVER
    if _RESOLVER is None:
        from .resolve import PdfResolver  # lazy: avoids a tools<->resolve import cycle

        _RESOLVER = PdfResolver(transport="stdio")
    return _RESOLVER


def _load_pdf(ref: Any) -> bytes:
    resolver = _resolver()
    data = resolver.resolve(ref, _current_principal.get())
    if resolver.transport == "http" and isinstance(ref, dict) and "blobId" in ref:
        consumed = _consumed_blobs.get()
        if consumed is not None:
            consumed.append(str(ref["blobId"]))  # deleted on completion (§K)
    return data


# Untrusted-PDF parse budget on the hosted transport ([OM-SEC-010], [OM-MCP-008]).
_PARSE_TIMEOUT_S = 30.0
_PARSE_MEMORY_MB = 2048
_MAX_PAGES = 3000  # per-call page ceiling; exceeding it returns OM-IO-005 (never silent truncation)


def set_max_pages(n: int) -> None:
    """Configure the per-call page ceiling ([OM-MCP-008])."""
    global _MAX_PAGES
    _MAX_PAGES = n


def _page_count(pdf_bytes: bytes) -> int:
    """Cheap page count (page tree only, no content streams). Top-level for subprocess pickling."""
    import io

    import pikepdf

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        return len(pdf.pages)


def _enforce_page_limit(pdf_bytes: bytes) -> None:
    """On the hosted transport, reject a document over the per-call page ceiling ([OM-MCP-008]).
    The count runs in the bounded subprocess too, so a malicious page tree can't hang/OOM the host.
    """
    if _resolver().transport != "http":
        return
    pages = _run_core(_page_count, pdf_bytes)
    if pages > _MAX_PAGES:
        raise ToolError("OM-IO-005", f"document has {pages} pages; per-call limit is {_MAX_PAGES}")


def _run_core(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a core parse verb. On the hosted transport it runs in a killable, memory-bounded
    subprocess so a malicious PDF that hangs/OOMs a C parser cannot take down the host (timeout →
    OM-IO-003, crash → OM-IO-010). On stdio the input is trusted-local, so it runs inline."""
    if _resolver().transport != "http":
        return func(*args, **kwargs)
    from .guard import bounded_call  # lazy: avoids a tools<->guard import cycle

    return bounded_call(
        func, args, kwargs=kwargs, timeout=_PARSE_TIMEOUT_S, memory_mb=_PARSE_MEMORY_MB
    )




@_guard
def om_inspect(pdf: Any, verify_origin: bool = False) -> dict[str, Any]:
    """Read-only: classify + profile the document (§I OM-MCP-010)."""
    data = _load_pdf(pdf)
    _enforce_page_limit(data)
    profile = _run_core(_inspect, data)
    payload = dict(profile["payload"])
    payload["originVerified"] = None  # §10 layer-3 check is M3; null = not checked
    return {
        "class": profile["class"],
        "classConfidence": profile["classConfidence"],
        "pages": profile["pages"],
        "payload": payload,
        "images": profile["images"],
        "textCoverage": profile["textCoverage"],
    }


@_guard
def om_read(pdf: Any, verify_origin: bool = True) -> dict[str, Any]:
    """Read-only: the cheap consumer path (§I OM-MCP-011)."""
    result = _run_core(_read, _load_pdf(pdf))
    # A hash-mismatched payload MUST be surfaced as null, never as trusted (OM-MCP-011).
    trusted = result.present and result.hash_valid is not False
    payload = result.payload if trusted else None
    return {
        "payload": payload,
        "payloadHash": payload_hash(payload) if payload is not None else None,
        "specVersion": (payload or {}).get("specVersion") if payload else None,
        "verification": {
            "hashValid": result.hash_valid,
            "originVerified": None,
            "signatureValid": None,
        },
    }


@_guard
def om_extract_text(
    pdf: Any, page_range: str | None = None, cursor: str | None = None, max_chars: int = 100_000
) -> dict[str, Any]:
    """Read-only, paginated text + best-effort tables (§I OM-MCP-012)."""
    data = _load_pdf(pdf)
    _enforce_page_limit(data)
    return dict(
        _run_core(_extract_text, data, page_range=page_range, max_chars=max_chars, cursor=cursor)
    )


@_guard
def om_extract_images(
    pdf: Any,
    out_dir: str | None = None,
    page_range: str | None = None,
    include_vector: bool = False,
) -> dict[str, Any]:
    """Read-only: manifest + local paths, never inline bytes (§I OM-MCP-013)."""
    dest = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="openom_img_"))
    data = _load_pdf(pdf)
    _enforce_page_limit(data)
    result = _run_core(_extract_images, data, out_dir=dest)
    manifest = []
    for img in result["images"]:
        if img["error"] is not None:
            continue
        path = img["path"]
        manifest.append({
            "xref": img["xref"],
            "width": img["width"],
            "height": img["height"],
            "colorspace": img["colorspace"],
            "hasSMask": img["hasSMask"],
            "mime": img["mime"],
            "bytes": Path(path).stat().st_size if path else 0,
            "contentHash": img["contentHash"],
            "path": path,
        })
    return {"manifest": manifest, "deduped": result["deduped"]}


@_guard
def om_validate(payload: Any, tolerances: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validator role: two-tier report (§I OM-MCP-014). A report is success even with errors."""
    tol = None
    if tolerances:
        tol = Tolerances(
            cap_rate_abs=tolerances.get("capRateAbs", 0.005),
            monetary_rel=tolerances.get("psfRel", tolerances.get("monetaryRel", 0.01)),
        )
    report = _validate(payload, schema=_load_schema(), tolerances=tol)
    return {
        "ok": report.ok,
        "errors": [dataclasses.asdict(f) for f in report.errors],
        "warnings": [dataclasses.asdict(f) for f in report.warnings],
        "info": [dataclasses.asdict(f) for f in report.info],
        "canonical": {"hash": payload_hash(payload)},
    }


@_guard
def om_embed(
    pdf: Any,
    payload: Any,
    out_path: str | None = None,
    badge: bool = False,
    source_doc_hash: bool = False,
) -> dict[str, Any]:
    """The only mutating tool: validate-then-embed, refuse on schema errors (§I OM-MCP-015)."""
    report = _validate(payload, schema=_load_schema())
    if not report.ok:
        raise ToolError(
            "OMV-E001",
            "payload has schema errors; embed refused",
            details={"errors": [dataclasses.asdict(f) for f in report.errors]},
        )
    asserted_date = str(payload.get("assertedDate", ""))
    out_bytes = _run_core(_embed, _load_pdf(pdf), payload, asserted_date=asserted_date, badge=badge)

    resolver = _resolver()
    if resolver.transport == "http" and resolver.blobstore is not None:
        # No client filesystem on the hosted transport — return the result as a TTL blob.
        stored = resolver.blobstore.put_result(out_bytes, _current_principal.get() or "")
        pdf_out = {"blobId": stored["blobId"], "presignedGet": stored["presignedGet"]}
    else:
        dest = Path(out_path) if out_path else Path(tempfile.mkstemp(suffix=".pdf")[1])
        dest.write_bytes(out_bytes)
        pdf_out = {"path": str(dest)}

    import io

    with pikepdf.open(io.BytesIO(out_bytes)) as doc:
        marker = read_marker(doc) or {}
    return {
        "pdf": pdf_out,
        "payloadHash": marker.get("payloadHash"),
        "supersedes": marker.get("supersedes"),
        "xmp": {
            "specName": marker.get("specName"),
            "specVersion": marker.get("specVersion"),
            "payloadFilename": marker.get("payloadFilename"),
            "payloadHash": marker.get("payloadHash"),
        },
    }


@_guard
def om_request_upload() -> dict[str, Any]:
    """Hosted-only: reserve a single-use presigned upload target for a PDF (§I, [OM-SEC-006]).

    Returns ``{blobId, presignedPut, expiresAt}``; the client PUTs bytes to ``presignedPut`` then
    passes ``{blobId}`` to any tool. On stdio there is no blob store → OM-IO-008.
    """
    resolver = _resolver()
    if resolver.transport != "http" or resolver.blobstore is None:
        raise ToolError("OM-IO-008", "om_request_upload requires the hosted transport")
    return dict(resolver.blobstore.create_upload(_current_principal.get() or ""))
