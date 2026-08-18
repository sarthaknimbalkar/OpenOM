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
import pytest

from _make_rich import make_rich_pdf
from _render import pages_pixel_identical
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


DPI = 300  # [OM-DoD-001](a) renders per-page rasters at 300 DPI


def _assert_nondestructive(original: bytes, embedded: bytes) -> None:
    """Full [OM-DoD-001](a) check: identical pixels (300 DPI, exact), page count, outline tree,
    link count + destinations, and text content + positions."""
    assert pages_pixel_identical(original, embedded, dpi=DPI), "300 DPI rasters differ"
    with pikepdf.open(io.BytesIO(original)) as a, pikepdf.open(io.BytesIO(embedded)) as b:
        assert len(a.pages) == len(b.pages)
    assert _toc(original) == _toc(embedded)  # identical bookmark/outline tree
    assert _words(original) == _words(embedded)  # text content + coordinates
    assert _links(original) == _links(embedded)  # link count + destinations
    assert _annot_count(original) == _annot_count(embedded)


# --- synthetic, CI-runnable ------------------------------------------------------------

def test_nondestructive_synthetic() -> None:
    rich = make_rich_pdf()
    _assert_nondestructive(rich, embed(rich, _sample(), asserted_date=FIXED_DATE))


def test_nondestructive_opens_without_repair_two_viewers() -> None:
    """[OM-DoD-001](a): the output opens without repair in >=2 independent parsers."""
    embedded = embed(make_rich_pdf(), _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(embedded)) as pdf:  # viewer 1: qpdf
        assert len(pdf.pages) >= 1
    doc = pymupdf.open(stream=embedded, filetype="pdf")  # viewer 2: mupdf
    try:
        assert doc.page_count >= 1
        assert doc.is_repaired is False  # mupdf did NOT have to rebuild the xref
    finally:
        doc.close()


# --- all 3 real classes (local; skipped without the corpus) ----------------------------

def test_nondestructive_native(native_om: bytes) -> None:
    _assert_nondestructive(native_om, embed(native_om, _sample(), asserted_date=FIXED_DATE))


def test_nondestructive_hybrid(hybrid_om: bytes) -> None:
    _assert_nondestructive(hybrid_om, embed(hybrid_om, _sample(), asserted_date=FIXED_DATE))


def test_nondestructive_scanned(scanned_om: bytes) -> None:
    _assert_nondestructive(scanned_om, embed(scanned_om, _sample(), asserted_date=FIXED_DATE))


# --- committed producer-diverse fixtures (#130): RUN IN CI, unlike the corpus tests above ------

@pytest.mark.parametrize("cls", ["native", "hybrid", "scanned"])
def test_nondestructive_producer(cls: str, producer_pdfs: dict[str, bytes]) -> None:
    """Non-destructiveness across object-stream/linearized (native), text+image (hybrid), and
    image-only (scanned) producer structures — the diversity the CI gate previously lacked."""
    original = producer_pdfs[cls]
    _assert_nondestructive(original, embed(original, _sample(), asserted_date=FIXED_DATE))
