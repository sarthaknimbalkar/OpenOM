"""Task 8: inspect / classify native·hybrid·scanned (spec §I, §X.3).

Real CRE marketing OMs are image-heavy and classify as 'hybrid'; a pure text layer is
'native' and a rasterized page set is 'scanned'. So 'native' is exercised with a synthetic
text-only PDF, 'hybrid' with the real CMYK OM, and 'scanned' with a synthesized raster PDF.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _make_scan import make_hybrid_pdf, make_ocr_scanned, make_scanned, make_text_pdf
from openom_core.embed import embed
from openom_core.inspect import classify, inspect

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def test_classify_branches() -> None:
    """The pure classifier, exercised directly (corpus-independent)."""
    assert classify(0.10, 0.0, 0.0) == "scanned"  # below scanned text threshold
    assert classify(0.90, 0.0, 0.0) == "native"  # text-rich, image-light
    assert classify(0.90, 0.9, 0.0) == "hybrid"  # text-rich but a full-page image (visible text)
    assert classify(0.50, 0.0, 5.0) == "hybrid"  # mid text, image-dense
    # #6: a high OCR-overlay fraction ⇒ scanned, even with full text coverage.
    assert classify(1.0, 1.0, 0.0, ocr_overlay_frac=0.9) == "scanned"
    assert classify(1.0, 1.0, 0.0, ocr_overlay_frac=0.0) == "hybrid"  # visible-text hybrid stays


def test_ocr_scanned_classifies_as_scanned() -> None:
    """#6: a scan with an INVISIBLE OCR text layer is 'scanned', not native/hybrid, despite having
    fully extractable text."""
    profile = inspect(make_ocr_scanned(make_text_pdf()))
    assert profile["class"] == "scanned"
    assert profile["textCoverage"] >= 0.85  # the OCR layer IS extractable — coverage is high
    assert profile["classConfidence"] > 0.0
    assert profile["ocrOverlay"] >= 0.6


def test_visible_text_hybrid_is_not_mistaken_for_an_ocr_scan() -> None:
    """The OCR rule keys on INVISIBLE text: a hybrid with visible text over a full-page image must
    still classify 'hybrid' (no false OCR-scan detection)."""
    assert inspect(make_hybrid_pdf())["class"] == "hybrid"


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


def test_scanned_real_corpus(scanned_om: bytes) -> None:
    """Real scanned OM from the corpus (local; skipped without it) — genuine scanned proof."""
    profile = inspect(scanned_om)
    assert profile["class"] == "scanned"
    assert profile["textCoverage"] < 0.2
    assert profile["images"]["count"] >= 1


def test_payload_reported_after_embed() -> None:
    embedded = embed(make_text_pdf(), _sample(), asserted_date="2026-08-15")
    profile = inspect(embedded)
    assert profile["payload"]["present"] is True
    assert profile["payload"]["hashValid"] is True
    assert profile["payload"]["specVersion"] == "0.1"
