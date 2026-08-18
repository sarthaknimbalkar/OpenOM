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


def test_reserved_signature_and_optional_identity_fields_accepted() -> None:
    # #117/#118/#114/#115: a well-formed signature + the reserved optional fields validate cleanly.
    p = copy.deepcopy(_sample())
    p["meta"]["signature"] = {"alg": "ed25519", "keyId": "did:key:z6Mk", "value": "BASE64SIG"}
    p.setdefault("property", {})["propertyType"] = "retail"
    p["assertedBy"]["website"] = "https://example.com"
    p["assertedBy"]["licenseJurisdiction"] = "US-CA"
    p["ext"] = {"acme": {"internalId": 42}}
    report = validate(p, schema=_schema())
    assert "OMV-E003" not in _codes(report.errors)
    assert report.ok is True


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


def test_warning_non_positive_noi() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["noi"] = -5000  # §H.3 W014: non-positive noi
    report = validate(bad)
    assert "OMW-W014" in _codes(report.warnings)
    assert report.ok is True  # warnings never block


def test_info_currency_defaulted() -> None:
    # valid-stnl omits currency -> assumed USD (OMI-I001, OM-DD-002).
    report = validate(_sample())
    assert "OMI-I001" in _codes(report.info)
    with_ccy = copy.deepcopy(_sample())
    with_ccy["currency"] = "USD"
    assert "OMI-I001" not in _codes(validate(with_ccy).info)


def test_warning_currency_absent_non_us() -> None:
    # #119: currency absent on an explicitly non-US property → OMW-W061 (US/absent stays info-only).
    non_us = copy.deepcopy(_sample())
    non_us["property"]["address"]["addressCountry"] = "GB"
    assert "OMW-W061" in _codes(validate(non_us).warnings)
    assert "OMW-W061" not in _codes(validate(_sample()).warnings)  # US base: no warning


def test_warning_cap_rate_outside_band() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["capRate"] = 0.30  # NOI/price still ~matches but 0.30 > band max 0.20
    bad["deal"]["noi"] = 555000  # keep W010 quiet: 555000/1850000 = 0.30
    assert "OMW-W013" in _codes(validate(bad).warnings)


def test_warning_proforma_without_asof() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["noiType"] = "pro-forma"
    del bad["deal"]["noiAsOfDate"]
    assert "OMW-W012" in _codes(validate(bad).warnings)


def test_warning_asserted_date_in_future() -> None:
    p = copy.deepcopy(_sample())  # assertedDate 2026-08-15
    assert "OMW-W032" in _codes(validate(p, as_of="2020-01-01").warnings)
    assert "OMW-W032" not in _codes(validate(p).warnings)  # silent without a processing date


def test_warning_noi_asof_after_asserted() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["noiAsOfDate"] = "2027-01-01"  # after assertedDate 2026-08-15
    assert "OMW-W033" in _codes(validate(bad).warnings)


def test_warning_expiration_before_commencement() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["expiration"] = "2010-01-01"  # <= commencement 2019-05-01
    assert "OMW-W034" in _codes(validate(bad).warnings)


def test_warning_gross_lease_no_responsibilities() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["leaseTypeAsserted"] = "gross"  # all flags false -> contradiction
    assert "OMW-W041" in _codes(validate(bad).warnings)


def test_warning_absolute_net_landlord_structural() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["leaseTypeAsserted"] = "absolute-net"
    bad["lease"]["landlordResponsibilities"]["roof"] = True
    assert "OMW-W041" in _codes(validate(bad).warnings)


def test_warning_self_supersede() -> None:
    from openom_core.canonical import payload_hash

    bad = copy.deepcopy(_sample())
    stripped = copy.deepcopy(bad)
    stripped["meta"].pop("supersedes", None)
    bad["meta"]["supersedes"] = payload_hash(stripped)  # points at itself minus the pointer
    assert "OMW-W050" in _codes(validate(bad).warnings)


def test_warning_source_verified() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["rentSchedule"][0]["source"] = "verified"
    assert "OMW-W060" in _codes(validate(bad).warnings)


def test_info_source_absent() -> None:
    p = copy.deepcopy(_sample())
    del p["lease"]["rentSchedule"][0]["source"]
    assert "OMI-I002" in _codes(validate(p).info)


def test_info_skipped_check() -> None:
    p = copy.deepcopy(_sample())
    del p["deal"]["noi"]  # capRate present but noi absent -> W010 can't run
    del p["deal"]["noiType"]
    del p["deal"]["noiAsOfDate"]
    assert "OMI-I003" in _codes(validate(p).info)


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


def test_warning_lease_term_mismatch() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["termMonths"] = 60  # far from expiration - commencement (~180 months)
    assert "OMW-W031" in _codes(validate(bad).warnings)


def test_warning_remaining_term_mismatch() -> None:
    bad = copy.deepcopy(_sample())
    bad["lease"]["remainingTermMonths"] = 12  # far from expiration - assertedDate (~92 months)
    assert "OMW-W030" in _codes(validate(bad).warnings)  # as_of defaults to assertedDate


def test_consistent_term_fields_clean() -> None:
    from datetime import date

    days_per_month = 30.4375
    comm, exp, asof = date(2019, 5, 1), date(2034, 4, 30), date(2026, 8, 15)
    ok = copy.deepcopy(_sample())
    ok["lease"]["termMonths"] = round((exp - comm).days / days_per_month, 1)
    ok["lease"]["remainingTermMonths"] = round((exp - asof).days / days_per_month, 1)
    codes = _codes(validate(ok).warnings)
    assert "OMW-W030" not in codes and "OMW-W031" not in codes


def test_as_of_override_drives_w030() -> None:
    p = copy.deepcopy(_sample())
    p["lease"]["remainingTermMonths"] = 92  # ~consistent as of assertedDate 2026-08-15
    # Move the processing date years forward -> remaining term is now way off -> W030.
    assert "OMW-W030" in _codes(validate(p, as_of="2033-06-01").warnings)


def test_configurable_tolerances() -> None:
    bad = copy.deepcopy(_sample())
    bad["deal"]["capRate"] = 0.065  # implied 0.0625; off by 0.0025
    assert "OMW-W010" not in _codes(validate(bad).warnings)  # within default 0.005
    strict = Tolerances(cap_rate_abs=0.001)
    assert "OMW-W010" in _codes(validate(bad, tolerances=strict).warnings)
