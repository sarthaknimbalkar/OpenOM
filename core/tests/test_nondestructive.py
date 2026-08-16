"""Task 7: embedding is visually + structurally non-destructive (spec §4 / §8a)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pikepdf

from _render import render_pages, ssim
from openom_core.embed import embed

SPEC = Path(__file__).resolve().parents[2] / "spec"
FIXED_DATE = "2026-08-15"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _annot_count(pdf_bytes: bytes) -> int:
    total = 0
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            if "/Annots" in page:
                total += len(page.Annots)
    return total


def test_visually_identical_hybrid(hybrid_om: bytes) -> None:
    embedded = embed(hybrid_om, _sample(), asserted_date=FIXED_DATE)
    before = render_pages(hybrid_om)
    after = render_pages(embedded)
    assert len(before) == len(after)
    for pa, pb in zip(before, after, strict=True):
        assert ssim(pa, pb) >= 0.9999


def test_structure_preserved_hybrid(hybrid_om: bytes) -> None:
    embedded = embed(hybrid_om, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(hybrid_om)) as p1, pikepdf.open(io.BytesIO(embedded)) as p2:
        assert len(p1.pages) == len(p2.pages)
        assert ("/Outlines" in p1.Root) == ("/Outlines" in p2.Root)  # bookmarks preserved
    assert _annot_count(hybrid_om) == _annot_count(embedded)  # links/annotations preserved
