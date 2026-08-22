"""The in-package schema copy MUST stay byte-identical to /spec (the single source).

openom-core ships spec/om-0.1.schema.json as package data at src/openom_core/om-0.1.schema.json so a
pip-installed wheel/sdist can load it via importlib.resources with no adjacent /spec dir (the
force-include-from-../spec approach could not produce a self-contained, installable sdist -> the
release pipeline's `python -m build` failed building the wheel from the sdist). /spec remains the
source of truth; this test is the drift lock. If it fails, re-copy:

    cp spec/om-0.1.schema.json core/src/openom_core/om-0.1.schema.json
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.schema import load_schema

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec" / "om-0.1.schema.json"
PACKAGED = ROOT / "core" / "src" / "openom_core" / "om-0.1.schema.json"


def test_packaged_schema_matches_spec_byte_for_byte() -> None:
    assert PACKAGED.exists(), (
        "in-package schema copy missing; run: "
        "cp spec/om-0.1.schema.json core/src/openom_core/om-0.1.schema.json"
    )
    assert PACKAGED.read_bytes() == SPEC.read_bytes(), (
        "core/src/openom_core/om-0.1.schema.json drifted from spec/om-0.1.schema.json; re-copy: "
        "cp spec/om-0.1.schema.json core/src/openom_core/om-0.1.schema.json"
    )


def test_load_schema_returns_the_packaged_copy() -> None:
    assert load_schema() == json.loads(SPEC.read_text(encoding="utf-8"))
