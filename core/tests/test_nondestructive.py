"""Task 7: embedding is visually + structurally non-destructive (spec §4 / §8a).

Two layers: a synthetic rich PDF that runs in CI (exact pixel equality + text/links/bookmarks
preserved), and the real hybrid OM (local, when the corpus is present) checked with worst-tile
SSIM so a localized change can't hide behind a good global average.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf

from _make_rich import make_rich_pdf
from _render import pages_pixel_identical, render_pages, tiled_ssim_min
from openom_core.embed import embed

SPEC = Path(__file__).resolve().parents[2] / "spec"
FIXED_DATE = "2026-08-15"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _words(pdf_bytes: bytes) -> list[list[tuple[Any, ...]]]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [list(page.get_text("words")) for page in doc]
    finally:
        doc.close()


def _links(pdf_bytes: bytes) -> list[list[tuple[Any, ...]]]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [
            [(lk.get("kind"), lk.get("uri"), lk.get("page")) for lk in page.get_links()]
            for page in doc
        ]
    finally:
        doc.close()


def _toc(pdf_bytes: bytes) -> list[list[Any]]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc.get_toc()
    finally:
        doc.close()


def _annot_count(pdf_bytes: bytes) -> int:
    total = 0
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            if "/Annots" in page:
                total += len(page.Annots)
    return total


# --- synthetic, CI-runnable ------------------------------------------------------------

def test_synthetic_pixels_byte_identical() -> None:
    rich = make_rich_pdf()
    embedded = embed(rich, _sample(), asserted_date=FIXED_DATE)
    assert pages_pixel_identical(rich, embedded, dpi=150)  # exact: any visual change fails


def test_synthetic_text_and_positions_preserved() -> None:
    rich = make_rich_pdf()
    embedded = embed(rich, _sample(), asserted_date=FIXED_DATE)
    assert _words(rich) == _words(embedded)  # content AND coordinates identical


def test_synthetic_links_and_bookmarks_preserved() -> None:
    rich = make_rich_pdf()
    embedded = embed(rich, _sample(), asserted_date=FIXED_DATE)
    assert _links(rich) == _links(embedded)  # internal GoTo + external URI destinations
    assert _toc(rich) == _toc(embedded)  # bookmarks
    assert _annot_count(rich) == _annot_count(embedded)


# --- real hybrid OM (local; skipped without the corpus) --------------------------------

def test_visually_identical_hybrid(hybrid_om: bytes) -> None:
    embedded = embed(hybrid_om, _sample(), asserted_date=FIXED_DATE)
    before = render_pages(hybrid_om, dpi=150)
    after = render_pages(embedded, dpi=150)
    assert len(before) == len(after)
    for pa, pb in zip(before, after, strict=True):
        assert tiled_ssim_min(pa, pb) >= 0.9999  # worst tile, not a masking global average


def test_structure_preserved_hybrid(hybrid_om: bytes) -> None:
    embedded = embed(hybrid_om, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(hybrid_om)) as p1, pikepdf.open(io.BytesIO(embedded)) as p2:
        assert len(p1.pages) == len(p2.pages)
        assert ("/Outlines" in p1.Root) == ("/Outlines" in p2.Root)
    assert _words(hybrid_om) == _words(embedded)  # text layer intact
    assert _links(hybrid_om) == _links(embedded)  # link destinations intact
    assert _annot_count(hybrid_om) == _annot_count(embedded)
