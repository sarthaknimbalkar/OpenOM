"""#148/#149: the canonical schema loader is cached (same object across calls, so the validator
cache in validate.py can key on identity) and equals the /spec single source."""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.schema import SCHEMA_NAME, load_schema

SPEC = Path(__file__).resolve().parents[2] / "spec" / SCHEMA_NAME


def test_load_schema_is_cached_and_matches_spec() -> None:
    a = load_schema()
    b = load_schema()
    assert a is b, "load_schema must return the same cached object (validator-cache key #148)"
    assert a["title"] == "openOM payload 0.1"
    assert a == json.loads(SPEC.read_text(encoding="utf-8")), "loader drifted from the /spec source"
