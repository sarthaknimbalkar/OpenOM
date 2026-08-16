"""M2 (#11): the committed pathology golden PDFs (encrypted / scanned / empty-payload) round-trip.

These goldens are Python-produced and read here by pikepdf; the same files are read by pdf-lib in
js/test/pathology.test.ts, so a Producer→Consumer round-trip is proven across both engines on the
nastiest base documents (an image-only scan, an empty-password-encrypted PDF, a minimal payload).
Regenerate with `python -m spec.vectors.build_pathologies`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openom_core.canonical import payload_hash
from openom_core.embed import read
from openom_core.inspect import inspect

PATH = Path(__file__).resolve().parents[2] / "spec" / "vectors" / "pathologies"
_MANIFEST = json.loads((PATH / "manifest.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _MANIFEST, ids=lambda c: c["name"])
def test_pathology_golden_round_trips(case: dict[str, Any]) -> None:
    pdf = (PATH / case["pdf"]).read_bytes()
    expected = json.loads((PATH / case["expected"]).read_text(encoding="utf-8"))
    result = read(pdf)
    assert result.present is True, f"{case['name']}: payload not detected"
    assert result.hash_valid is True, f"{case['name']}: hash did not verify"
    assert result.payload == expected, f"{case['name']}: payload mismatch"
    # The embedded marker hash equals the canonical hash of the payload we put in.
    assert payload_hash(result.payload) == payload_hash(expected)
    if case.get("class"):
        assert inspect(pdf)["class"] == case["class"]


def test_encrypted_golden_is_actually_encrypted() -> None:
    import io

    import pikepdf

    pdf = (PATH / "encrypted.pdf").read_bytes()
    with pikepdf.open(io.BytesIO(pdf)) as doc:  # opens via empty password
        assert doc.is_encrypted, "the encrypted golden must actually be encrypted"
