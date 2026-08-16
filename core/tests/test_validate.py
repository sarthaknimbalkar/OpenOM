"""Task 10: two-tier validator + consistency checks (spec §H)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from openom_core.validate import Tolerances, validate

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


def test_warning_monthly_rent_mismatch() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][0]["monthlyRent"] = 5000  # annual 115625 / 12 ≈ 9635
    report = validate(bad)
    assert "OMW-W025" in _codes(report.warnings)


def test_warning_escalation_mismatch() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][1]["escalationFromPrior"] = 0.25  # actual step ≈ 0.10
    report = validate(bad)
    assert "OMW-W023" in _codes(report.warnings)


def test_warning_period_outside_lease_term() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][0]["periodStart"] = "2010-01-01"  # before commencement 2019-05-01
    report = validate(bad)
    assert "OMW-W026" in _codes(report.warnings)


def test_warning_net_lease_but_landlord_pays() -> None:
    bad = copy.deepcopy(_sample())  # NNN
    bad["lease"]["landlordResponsibilities"]["taxes"] = True
    report = validate(bad)
    assert "OMW-W040" in _codes(report.warnings)


def test_warning_non_positive_rent() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][0]["annualRent"] = 0  # no abatement flag
    report = validate(bad)
    assert "OMW-W014" in _codes(report.warnings)


def test_info_proforma_noi() -> None:
    pro = copy.deepcopy(_sample())
    pro["deal"]["noiType"] = "pro-forma"
    report = validate(pro)
    assert "OMI-I001" in _codes(report.info)
    assert report.ok is True  # info never blocks


def test_findings_carry_requirement_and_are_ordered() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["capRate"] = 0.09
    bad["lease"]["rentSchedule"][0]["monthlyRent"] = 5000
    report = validate(bad)
    assert all(f.requirement for f in report.warnings)  # §H.1 back-reference present
    codes = [(f.code, f.path) for f in report.warnings]
    assert codes == sorted(codes)  # deterministic ordering


def test_warning_price_per_sf_mismatch() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["pricePerSF"] = 999  # implied 1850000/9100 ≈ 203
    assert "OMW-W011" in _codes(validate(bad).warnings)


def test_warning_period_ends_after_expiration() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][1]["periodEnd"] = "2099-01-01"  # past expiration 2034-04-30
    assert "OMW-W026" in _codes(validate(bad).warnings)


def test_schema_free_error_checks() -> None:
    missing = copy.deepcopy(_sample())
    del missing["deal"]["noiType"]  # noi present, noiType missing, no schema supplied
    assert "OMV-E002" in _codes(validate(missing).errors)
    signed = copy.deepcopy(_sample())
    signed["meta"]["signature"] = {"alg": "x"}
    assert "OMV-E003" in _codes(validate(signed).errors)


def test_error_bad_supersedes_via_schema() -> None:
    bad = copy.deepcopy(_sample())
    bad["meta"]["supersedes"] = "sha256:nothex"
    assert "OMV-E010" in _codes(validate(bad, schema=_schema()).errors)


def test_malformed_date_does_not_crash() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][1]["periodStart"] = "not-a-date"
    validate(bad)  # unparseable dates are skipped, not fatal


def test_configurable_tolerances() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["capRate"] = 0.065  # implied 0.0625; off by 0.0025
    assert "OMW-W010" not in _codes(validate(bad).warnings)  # within default 0.005
    strict = Tolerances(cap_rate_abs=0.001)
    assert "OMW-W010" in _codes(validate(bad, tolerances=strict).warnings)
