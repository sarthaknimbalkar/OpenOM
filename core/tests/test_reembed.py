"""Task 6: idempotent re-embed + supersedes chain (spec §D.4)."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from openom_core.canonical import canonicalize, payload_hash
from openom_core.embed import embed, read
from openom_core.xmp import read_marker

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


@pytest.fixture
def base_pdf() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _marker(pdf_bytes: bytes) -> dict[str, str]:
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        m = read_marker(pdf)
        assert m is not None
        return m


def test_reprice_sets_supersedes(base_pdf: bytes) -> None:
    v1 = _sample()
    v2 = copy.deepcopy(v1)
    v2["deal"]["askingPrice"] = 1795000  # a price reduction — the common re-embed event

    e1 = embed(base_pdf, v1, asserted_date="2026-08-15")
    e2 = embed(e1, v2, asserted_date="2026-09-01")

    assert canonicalize(read(e2).payload) == canonicalize(v2)  # type: ignore[arg-type]
    assert _marker(e2)["supersedes"] == payload_hash(v1)
    assert read(e2).hash_valid is True
    with pikepdf.open(io.BytesIO(e2)) as pdf:
        assert len(pdf.Root.AF) == 1
        assert list(pdf.attachments).count("om.json") == 1


def test_identical_reembed_is_noop_no_self_supersede(base_pdf: bytes) -> None:
    v1 = _sample()
    e1 = embed(base_pdf, v1, asserted_date="2026-08-15")
    e2 = embed(e1, v1, asserted_date="2026-09-01")  # same payload
    assert "supersedes" not in _marker(e2)  # no self-supersede (cf. OMW-W050)
    assert read(e2).hash_valid is True


def test_supersedes_cleared_when_reprice_then_reverts(base_pdf: bytes) -> None:
    v1 = _sample()
    v2 = copy.deepcopy(v1)
    v2["deal"]["askingPrice"] = 1795000

    e1 = embed(base_pdf, v1, asserted_date="2026-08-15")
    e2 = embed(e1, v2, asserted_date="2026-09-01")  # supersedes = hash(v1)
    assert "supersedes" in _marker(e2)
    e3 = embed(e2, v2, asserted_date="2026-09-02")  # identical to v2 -> stale chain cleared
    assert "supersedes" not in _marker(e3)
