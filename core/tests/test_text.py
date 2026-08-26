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


def _two_page_with_table_on_p2() -> bytes:
    """Page 1: lots of text (forces a first window to cover only page 1). Page 2: a ruled grid table
    pymupdf.find_tables detects."""
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), ("page one filler text " * 20 + "\n") * 8, fontsize=11)
    p2 = doc.new_page()
    # draw a 3x3 ruled grid + cell text so find_tables sees a table
    x0, y0, step = 72, 72, 60
    for k in range(4):
        p2.draw_line((x0, y0 + k * step), (x0 + 3 * step, y0 + k * step))
        p2.draw_line((x0 + k * step, y0), (x0 + k * step, y0 + 3 * step))
    for r in range(3):
        for c in range(3):
            p2.insert_text((x0 + c * step + 6, y0 + r * step + 20), f"r{r}c{c}", fontsize=9)
    try:
        return doc.tobytes()
    finally:
        doc.close()


def test_tables_scoped_to_the_paginated_window() -> None:
    """[Ma6] Tables are emitted only for pages the current text window covers, not the whole doc on
    every paginated call."""
    pdf = _two_page_with_table_on_p2()
    full = extract_text(pdf, max_chars=1_000_000)
    all_table_pages = {t["page"] for t in full["tables"]}
    if 2 not in all_table_pages:
        pytest.skip("find_tables did not detect the drawn grid in this pymupdf build")
    # A small first window covers only page 1 → it must NOT carry page-2 tables.
    first = extract_text(pdf, max_chars=40)
    assert first["truncated"] and all(t["page"] == 1 for t in first["tables"])
    assert all(t["page"] != 2 for t in first["tables"])


def test_cursor_is_scoped_to_page_range_not_just_bytes() -> None:
    # A cursor minted for one page selection must be rejected when replayed with a different
    # page_range (its offset is into the concatenation of the SELECTED pages) - else it silently
    # returns misaligned text. The same page_range still accepts its own cursor.
    pdf = _two_page_with_table_on_p2()
    c = extract_text(pdf, page_range="1", max_chars=20)["nextCursor"]
    assert c
    with pytest.raises(CursorError):
        extract_text(pdf, page_range="2", max_chars=20, cursor=c)
    # same selection round-trips fine
    again = extract_text(pdf, page_range="1", max_chars=20, cursor=c)
    assert "text" in again


def test_tables_not_duplicated_across_a_window_boundary() -> None:
    """A page whose text straddles a paginated window boundary must have its tables emitted in
    exactly one window. Walking the whole pagination must yield the same tables as a single call."""
    pdf = _two_page_with_table_on_p2()
    full = extract_text(pdf, max_chars=1_000_000)
    if not any(t["page"] == 2 for t in full["tables"]):
        pytest.skip("find_tables did not detect the drawn grid in this pymupdf build")

    def key(t: dict[str, object]) -> tuple[object, str]:
        return (t["page"], repr(t["rows"]))

    expected = sorted(key(t) for t in full["tables"])
    # Small windows so a boundary lands inside the table page; accumulate tables across every call.
    got: list[tuple[object, str]] = []
    cursor: str | None = None
    for _ in range(50):  # generous cap; the doc paginates in far fewer
        page = extract_text(pdf, max_chars=30, cursor=cursor)
        got.extend(key(t) for t in page["tables"])
        cursor = page["nextCursor"]
        if cursor is None:
            break
    assert sorted(got) == expected  # every table once - no boundary duplication, no loss
