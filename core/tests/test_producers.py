"""Task 12: embed round-trips across producer-diverse base PDFs (structural variety).

Real producer diversity (InDesign/Word/Buildout/scan) lives in the confidential corpus; these
synthetic bases exercise the structural variety that matters for the wire format - multi-page,
pre-existing XMP, object streams, non-Letter page size - so producer robustness runs in CI.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from openom_core.embed import embed, read

SPEC = Path(__file__).resolve().parents[2] / "spec"
FIXED_DATE = "2026-08-15"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _save(pdf: pikepdf.Pdf, **kwargs: Any) -> bytes:
    buf = io.BytesIO()
    pdf.save(buf, **kwargs)
    return buf.getvalue()


def _blank() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return _save(pdf)


def _multipage() -> bytes:
    pdf = pikepdf.new()
    for _ in range(3):
        pdf.add_blank_page(page_size=(612, 792))
    return _save(pdf)


def _a4() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))  # A4 points
    return _save(pdf)


def _object_streams() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return _save(pdf, object_stream_mode=pikepdf.ObjectStreamMode.generate)


def _with_existing_xmp() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = "Existing Offering Title"
    return _save(pdf)


_PRODUCERS: list[tuple[str, Callable[[], bytes]]] = [
    ("blank", _blank),
    ("multipage", _multipage),
    ("a4", _a4),
    ("object-streams", _object_streams),
    ("existing-xmp", _with_existing_xmp),
]


@pytest.mark.parametrize("label,factory", _PRODUCERS, ids=[p[0] for p in _PRODUCERS])
def test_embed_roundtrips_across_producers(label: str, factory: Callable[[], bytes]) -> None:
    result = read(embed(factory(), _sample(), asserted_date=FIXED_DATE))
    assert result.present is True, label
    assert result.hash_valid is True, label


def test_existing_xmp_and_marker_coexist() -> None:
    """Embedding into a doc with existing XMP preserves it AND adds a readable omspec marker."""
    out = embed(_with_existing_xmp(), _sample(), asserted_date=FIXED_DATE)
    assert read(out).hash_valid is True
    with pikepdf.open(io.BytesIO(out)) as pdf, pdf.open_metadata(
        set_pikepdf_as_editor=False
    ) as meta:
        assert meta.get("dc:title") == "Existing Offering Title"
