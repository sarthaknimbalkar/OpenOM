"""#113: negative-state golden vectors - the FAILURE paths a conformant consumer must reproduce, not
just the L1 happy path. Reads spec/vectors/negatives/manifest.json (shared with the JS core) and
asserts each golden yields its expected read outcome. In the Python core, JS `hash-mismatch` == a
present payload with hash_valid False ([OM-VAL-006])."""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.embed import read

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors"
MANIFEST = json.loads((VECTORS / "negatives" / "manifest.json").read_text(encoding="utf-8"))


def test_negative_state_goldens_read_as_expected() -> None:
    assert MANIFEST["cases"], "negatives suite is empty"
    for case in MANIFEST["cases"]:
        pdf = (VECTORS / case["pdf"]).read_bytes()
        result = read(pdf)
        if case["expectState"] == "hash-mismatch":
            assert result.present is True, case["name"]
            assert result.hash_valid is False, case["name"]
        else:  # pragma: no cover - only hash-mismatch exists today
            raise AssertionError(f"unhandled expectState {case['expectState']}")
