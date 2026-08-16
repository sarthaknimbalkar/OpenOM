"""Task 3: the conformance sample matrix (spec §B [OM-VEC-004]).

Drives spec/samples/manifest.json through the schema-tier validator. Both implementations
MUST reproduce these outcomes (Track B runs the same manifest); this is the schema half of
the anti-fork contract. Formats are asserted (calendar-strict dates), matching Track B's
ajv-formats(mode: full).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
SAMPLES = SPEC / "samples"


def _schema() -> dict[str, Any]:
    return json.loads((SPEC / "om-0.1.schema.json").read_text(encoding="utf-8"))


def _sample(name: str) -> dict[str, Any]:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def _manifest() -> list[dict[str, Any]]:
    return json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))["samples"]


@pytest.mark.parametrize("entry", _manifest(), ids=lambda e: e["name"])
def test_sample_matrix(entry: dict[str, Any]) -> None:
    schema = _schema()
    report = validate(_sample(f"{entry['name']}.json"), schema=schema)
    codes = [f.code for f in report.errors]
    if entry["valid"]:
        assert report.errors == [], f"{entry['name']} should validate clean, got {codes}"
        assert report.ok is True
    else:
        assert not report.ok, f"{entry['name']} should be blocked"
        for expected in entry["errorCodes"]:
            assert expected in codes, f"{entry['name']} missing {expected}; got {codes}"
    # Consistency-tier parity: warning codes both implementations must reproduce.
    warn_codes = [f.code for f in report.warnings]
    for expected in entry.get("warningCodes", []):
        assert expected in warn_codes, f"{entry['name']}: missing {expected} in {warn_codes}"


def test_forward_compatibility_unknown_member_accepted() -> None:
    """[OM-VER-003]: unknown OPTIONAL members are permitted (schema stays open)."""
    payload = _sample("valid-stnl.json")
    payload["someUnknownFutureField"] = {"nested": [1, 2, 3]}
    payload["property"]["anotherUnknown"] = "ok"
    report = validate(payload, schema=_schema())
    assert report.errors == []


def test_bad_calendar_date_rejected() -> None:
    """Impossible-but-regex-valid dates fail (calendar-strict parity with ajv mode: full)."""
    payload = _sample("valid-proforma.json")
    payload["assertedDate"] = "2026-02-30"  # Feb 30 does not exist
    report = validate(payload, schema=_schema())
    assert not report.ok
