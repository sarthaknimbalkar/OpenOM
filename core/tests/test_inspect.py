"""Task 8: inspect / classify native·hybrid·scanned (spec §I, §X.3).

Real CRE marketing OMs are image-heavy and classify as 'hybrid'; a pure text layer is
'native' and a rasterized page set is 'scanned'. So 'native' is exercised with a synthetic
text-only PDF, 'hybrid' with the real CMYK OM, and 'scanned' with a synthesized raster PDF.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _make_scan import make_scanned, make_text_pdf
from openom_core.embed import embed
from openom_core.inspect import classify, inspect

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def test_classify_branches() -> None:
    """The pure classifier, exercised directly (corpus-independent)."""
    assert classify(0.10, 0.0, 0.0) == "scanned"  # below scanned text threshold
    assert classify(0.90, 0.0, 0.0) == "native"  # text-rich, image-light
    assert classify(0.90, 0.9, 0.0) == "hybrid"  # text-rich but a full-page image
    assert classify(0.50, 0.0, 5.0) == "hybrid"  # mid text, image-dense


def test_native_synthetic() -> None:
    profile = inspect(make_text_pdf())
    assert profile["class"] == "native"
    assert profile["textCoverage"] >= 0.85
    assert profile["images"]["count"] == 0
    assert profile["payload"]["present"] is False


def test_hybrid_real_cmyk(hybrid_om: bytes) -> None:
    profile = inspect(hybrid_om)
    assert profile["class"] == "hybrid"
    assert profile["images"]["hasSMask"] is True
    assert "DeviceCMYK" in profile["images"]["colorspaces"]


def test_scanned_synthetic() -> None:
    # Rasterize a synthetic text PDF -> image-only pages, no corpus needed.
    profile = inspect(make_scanned(make_text_pdf()))
    assert profile["class"] == "scanned"
    assert profile["textCoverage"] < 0.2
    assert profile["images"]["count"] >= 1


def test_payload_reported_after_embed() -> None:
    embedded = embed(make_text_pdf(), _sample(), asserted_date="2026-08-15")
    profile = inspect(embedded)
    assert profile["payload"]["present"] is True
    assert profile["payload"]["hashValid"] is True
    assert profile["payload"]["specVersion"] == "0.1"
