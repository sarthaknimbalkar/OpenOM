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

import dataclasses
import json
import tempfile
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import pikepdf
from openom_core.canonical import payload_hash
from openom_core.embed import embed as _embed
from openom_core.embed import read as _read
from openom_core.errors import CanonicalizationError, PayloadTooLargeError
from openom_core.images import extract_images as _extract_images
from openom_core.inspect import inspect as _inspect
from openom_core.text import CursorError, PageRangeError
from openom_core.text import extract_text as _extract_text
from openom_core.validate import Tolerances
from openom_core.validate import validate as _validate
from openom_core.xmp import read_marker

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "spec" / "om-0.1.schema.json"


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
    """Map expected failures to the error envelope; never raise out of a tool (OM-MCP-004)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except ToolError as exc:
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

    return wrapper


def _load_pdf(ref: Any) -> bytes:
    if not isinstance(ref, dict):
        raise ToolError("OM-IO-008", "pdf must be a PdfRef object (one of path/url/blobId)")
    if "path" in ref:
        try:
            return Path(ref["path"]).read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
            raise ToolError("OM-IO-010", f"cannot read PDF at path: {exc}") from exc
    if "url" in ref or "blobId" in ref:
        raise ToolError(
            "OM-IO-008", "url/blobId need the hosted transport (M3); stdio accepts 'path' only"
        )
    raise ToolError("OM-IO-008", "PdfRef must have exactly one of path/url/blobId")


def _load_schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return data


@_guard
def om_inspect(pdf: Any, verify_origin: bool = False) -> dict[str, Any]:
    """Read-only: classify + profile the document (§I OM-MCP-010)."""
    profile = _inspect(_load_pdf(pdf))
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
    result = _read(_load_pdf(pdf))
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
    return dict(_extract_text(data, page_range=page_range, max_chars=max_chars, cursor=cursor))


@_guard
def om_extract_images(
    pdf: Any,
    out_dir: str | None = None,
    page_range: str | None = None,
    include_vector: bool = False,
) -> dict[str, Any]:
    """Read-only: manifest + local paths, never inline bytes (§I OM-MCP-013)."""
    dest = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="openom_img_"))
    result = _extract_images(_load_pdf(pdf), out_dir=dest)
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
    out_bytes = _embed(_load_pdf(pdf), payload, asserted_date=asserted_date, badge=badge)
    dest = Path(out_path) if out_path else Path(tempfile.mkstemp(suffix=".pdf")[1])
    dest.write_bytes(out_bytes)

    import io

    with pikepdf.open(io.BytesIO(out_bytes)) as doc:
        marker = read_marker(doc) or {}
    return {
        "pdf": {"path": str(dest)},
        "payloadHash": marker.get("payloadHash"),
        "supersedes": marker.get("supersedes"),
        "xmp": {
            "specName": marker.get("specName"),
            "specVersion": marker.get("specVersion"),
            "payloadFilename": marker.get("payloadFilename"),
            "payloadHash": marker.get("payloadHash"),
        },
    }
