# SPDX-License-Identifier: MIT
"""Deterministic text extraction (spec §I om_extract_text). Locate + read the text layer and
best-effort tables; paginate by an opaque, input-scoped cursor. Zero inference, no network.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
from typing import Any, TypedDict

from .errors import EncryptedPdfError

try:
    import pymupdf
except ImportError:  # PyMuPDF (AGPL) is an optional [render] extra
    pymupdf = None

_RENDER_HINT = "text extraction requires PyMuPDF: pip install 'openom-core[render]'"


class TextResult(TypedDict):
    text: str
    tables: list[dict[str, Any]]
    pageRange: str
    truncated: bool
    nextCursor: str | None


class PageRangeError(ValueError):
    """Malformed or out-of-bounds page range (maps to OM-IO-012)."""


class CursorError(ValueError):
    """Malformed cursor or cursor presented for a different input (maps to OM-IO-013)."""


def _parse_page_range(spec: str | None, page_count: int) -> list[int]:
    """1-indexed inclusive '3' | '1-5' | '2,4,7' → sorted 0-based indices. None → all pages."""
    if spec is None:
        return list(range(page_count))
    indices: set[int] = set()
    try:
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                lo_s, hi_s = part.split("-", 1)
                lo, hi = int(lo_s), int(hi_s)
            else:
                lo = hi = int(part)
            if lo < 1 or hi < lo:
                raise PageRangeError(f"invalid page range: {part!r}")
            indices.update(range(lo - 1, hi))
    except ValueError as exc:
        raise PageRangeError(f"malformed page range: {spec!r}") from exc
    if any(i >= page_count for i in indices):
        raise PageRangeError(f"page range out of bounds (doc has {page_count} pages)")
    return sorted(indices)


def _input_tag(pdf_bytes: bytes, pages: list[int]) -> str:
    # Scope the cursor to BOTH the PDF bytes AND the resolved page selection: the offset is a char
    # position into the concatenation of the SELECTED pages, so replaying a cursor with a different
    # page_range must be rejected (OM-IO-013) rather than silently slicing into different text.
    h = hashlib.sha256(pdf_bytes)
    h.update(repr(pages).encode("utf-8"))
    return h.hexdigest()[:16]


def _encode_cursor(tag: str, offset: int) -> str:
    raw = json.dumps({"h": tag, "off": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str, tag: str) -> int:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if data["h"] != tag:  # cursor scoped to a specific input (OM-MCP-005)
            raise CursorError("cursor does not match this input")
        return int(data["off"])
    except CursorError:
        raise
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad cursor
        raise CursorError("malformed cursor") from exc


def extract_text(
    pdf_bytes: bytes,
    *,
    page_range: str | None = None,
    max_chars: int = 100_000,
    cursor: str | None = None,
) -> TextResult:
    """Extract paginated text + best-effort tables for the selected pages (§I OM-MCP-012)."""
    if pymupdf is None:
        raise ImportError(_RENDER_HINT)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass:  # password-protected: refuse cleanly, not a "document closed" ValueError
        doc.close()
        raise EncryptedPdfError
    try:
        pages = _parse_page_range(page_range, doc.page_count)
        tag = _input_tag(pdf_bytes, pages)
        start = _decode_cursor(cursor, tag) if cursor else 0

        # Concatenate the selected pages' text with a form-feed page separator (deterministic).
        texts = [doc.load_page(i).get_text("text") for i in pages]
        full = "\f".join(texts)
        window = full[start : start + max_chars]
        end = start + len(window)
        truncated = end < len(full)

        # [Ma6] Emit tables ONLY for the pages the current text window covers - not the whole
        # selection on every paginated call (which re-sent the whole doc's tables each page:
        # unbounded + duplicated). Map each page's char span in `full` (+1 per \f) vs [start, end).
        tables: list[dict[str, Any]] = []
        pos = 0
        for idx, page_text in enumerate(texts):
            page_i = pages[idx]
            span_start, span_end = pos, pos + len(page_text)
            pos = span_end + 1  # account for the "\f" separator
            # Emit a page's tables in exactly ONE window - the one its text STARTS in. Paginated
            # windows tile contiguously from the cursor ([0,e1),[e1,e2),...), so every page's start
            # falls in exactly one window. Testing intersection instead double-emits a page that
            # straddles the boundary (it overlaps both the ending window and the beginning one).
            if not (start <= span_start < end):
                continue
            try:
                # find_tables() prints a one-time "Consider using pymupdf_layout" advisory to
                # sys.stdout; swallow it so the CLI/MCP stdout stays pure JSON. (A C-level SIGABRT
                # inside find_tables is NOT catchable here - the MCP/CLI callers isolate the
                # parse in a killable subprocess; this try/except only covers ordinary exceptions.)
                with contextlib.redirect_stdout(io.StringIO()):
                    found = doc.load_page(page_i).find_tables()
            except Exception:  # noqa: BLE001 - a table extraction error is non-fatal; skip this page
                continue
            for tbl in found.tables:
                tables.append({"page": page_i + 1, "rows": tbl.extract()})

        return {
            "text": window,
            "tables": tables,
            "pageRange": page_range or f"1-{doc.page_count}",
            "truncated": truncated,
            "nextCursor": _encode_cursor(tag, end) if truncated else None,
        }
    finally:
        doc.close()
