"""Cross-implementation rejection conformance (§C.1) - the rejection half of the anti-fork
oracle. Both implementations MUST reject each malformed input with the SAME OM-IO-* code; the
JS side runs the identical manifest (js/test/rejections.test.ts). The happy-path vectors prove
byte-identity; these prove the two engines agree on what to REFUSE.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openom_core.canonical import canonicalize
from openom_core.errors import CanonicalizationError

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors"
REJECTIONS = VECTORS / "rejections"


def _cases() -> list[tuple[str, str, str]]:
    manifest = json.loads((REJECTIONS / "manifest.json").read_text(encoding="utf-8"))
    return [(c["name"], c["input"], c["code"]) for c in manifest["cases"]]


@pytest.mark.parametrize("name,inp,code", _cases(), ids=[c[0] for c in _cases()])
def test_rejection_conformance(name: str, inp: str, code: str) -> None:
    value: Any = json.loads((VECTORS / inp).read_text(encoding="utf-8"))
    with pytest.raises(CanonicalizationError) as ei:
        canonicalize(value)
    assert ei.value.code == code, f"{name}: expected {code}, got {ei.value.code}"
