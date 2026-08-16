"""Task 10: two-tier validator + consistency checks (spec §H)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from openom_core.validate import validate

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _schema() -> dict[str, Any]:
    return json.loads((SPEC / "om-0.1.schema.json").read_text(encoding="utf-8"))


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _codes(findings: list[Any]) -> set[str]:
    return {f.code for f in findings}


def test_valid_sample_clean() -> None:
    report = validate(_sample(), schema=_schema())
    assert report.errors == []
    assert report.warnings == []  # the sample's math is internally consistent
    assert report.ok is True


def test_error_missing_noitype() -> None:
    report = validate(_load_invalid("invalid-missing-noitype"), schema=_schema())
    assert "OMV-E002" in _codes(report.errors)
    assert report.ok is False


def test_error_populated_signature() -> None:
    report = validate(_load_invalid("invalid-populated-signature"), schema=_schema())
    assert "OMV-E003" in _codes(report.errors)


def test_error_caprate_percentage_schema() -> None:
    report = validate(_load_invalid("invalid-caprate-percentage"), schema=_schema())
    assert "OMV-E001" in _codes(report.errors)  # capRate 6.25 > schema max 1


def test_warning_cap_rate_mismatch() -> None:
    bad = _sample()
    bad["deal"]["capRate"] = 0.09  # implied is 115625/1850000 = 0.0625
    report = validate(bad)  # no schema -> warning tier only
    assert "OMW-W010" in _codes(report.warnings)
    assert report.ok is True  # warnings never block


def test_warning_rent_schedule_gap() -> None:
    bad = _sample()
    bad["lease"]["rentSchedule"][1]["periodStart"] = "2030-01-01"  # hole after 2029-04-30
    report = validate(bad)
    assert "OMW-W021" in _codes(report.warnings)


def test_warning_rent_schedule_overlap() -> None:
    bad = _sample()
    bad["lease"]["rentSchedule"][1]["periodStart"] = "2028-01-01"  # before prior end 2029-04-30
    report = validate(bad)
    assert "OMW-W022" in _codes(report.warnings)


def _load_invalid(name: str) -> dict[str, Any]:
    return json.loads((SPEC / "samples" / f"{name}.json").read_text(encoding="utf-8"))


def test_warning_year1_rent_vs_noi() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][0]["annualRent"] = 90000  # far from noi 115625
    report = validate(bad)
    assert "OMW-W020" in _codes(report.warnings)
