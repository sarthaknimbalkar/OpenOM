"""om_extract_text core verb (§I OM-MCP-012): pagination, page ranges, cursor scoping."""

from __future__ import annotations

import pymupdf
import pytest

from _make_scan import make_text_pdf
from openom_core.text import CursorError, PageRangeError, extract_text


def _other_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "totally different content here " * 6, fontsize=11)
    try:
        return doc.tobytes()
    finally:
        doc.close()


def test_extract_all_text() -> None:
    r = extract_text(make_text_pdf())
    assert r["text"]
    assert r["truncated"] is False
    assert r["nextCursor"] is None
    assert isinstance(r["tables"], list)


def test_pagination_cursor_roundtrip() -> None:
    pdf = make_text_pdf()
    first = extract_text(pdf, max_chars=40)
    assert first["truncated"] is True
    assert first["nextCursor"]
    second = extract_text(pdf, max_chars=40, cursor=first["nextCursor"])
    assert second["text"] and second["text"] != first["text"]


def test_page_range_parsing() -> None:
    pdf = make_text_pdf()  # single page
    assert extract_text(pdf, page_range="1")["text"]
    for bad in ("9-9", "abc", "5-1", "0"):
        with pytest.raises(PageRangeError):
            extract_text(pdf, page_range=bad)


def test_cursor_is_scoped_to_input() -> None:
    a = make_text_pdf()
    cur = extract_text(a, max_chars=20)["nextCursor"]
    assert cur is not None
    with pytest.raises(CursorError):
        extract_text(a, cursor="not-a-real-cursor")
    with pytest.raises(CursorError):
        extract_text(_other_pdf(), cursor=cur)  # cursor tagged for `a`, presented for another PDF
