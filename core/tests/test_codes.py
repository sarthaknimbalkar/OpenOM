"""#151: spec/codes.json is the CANONICAL finding-code registry (code -> requirement + severity).
The Python and JS cores each hand-maintain a map; this drift-locks the Python one to the registry so
a new/changed code can't silently diverge (the JS side is locked by js/test/codes.test.ts)."""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.validate import _REQUIREMENT, _SEVERITY

REGISTRY = json.loads(
    (Path(__file__).resolve().parents[2] / "spec" / "codes.json").read_text(encoding="utf-8")
)["codes"]


def test_python_requirement_map_matches_registry() -> None:
    assert _REQUIREMENT == {code: e["requirement"] for code, e in REGISTRY.items()}


def test_registry_severity_matches_the_code_prefix() -> None:
    for code, e in REGISTRY.items():
        assert e["severity"] == _SEVERITY[code.split("-")[1][0]], code


def test_every_code_is_self_describing() -> None:
    """[Po10] codes.json must carry a human message per code so it is usable stand-alone."""
    missing = sorted(c for c, e in REGISTRY.items() if not e.get("message", "").strip())
    assert not missing, f"codes.json entries without a message: {missing}"
