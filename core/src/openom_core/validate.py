# SPDX-License-Identifier: MIT
"""Two-tier payload validation (spec §H): schema errors block, consistency warnings never do.

Errors (``OMV-E###``) come from JSON Schema plus the noi/signature rules; warnings
(``OMW-W###``) are internal-consistency checks against configurable tolerances (§H.4
[OM-ERR-014]); info (``OMI-I###``) is advisory context. Warnings/info NEVER block and MUST NOT
mutate the payload. Tooling checks internal consistency only — market truth is out of scope
forever. Every finding carries a requirement back-reference (§H.1) and findings are emitted in
deterministic (code, path) order.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from .errors import Finding, Severity

# Requirement back-references (§H.1) keyed by finding code.
_REQUIREMENT = {
    "OMV-E001": "OM-DD-001",
    "OMV-E002": "OM-DD",
    "OMV-E003": "OM-ERR-090",
    "OMV-E010": "OM-ERR-013",
    "OMW-W010": "OM-CONS-010",
    "OMW-W011": "OM-CONS-011",
    "OMW-W014": "OM-CONS-014",
    "OMW-W020": "OM-CONS-020",
    "OMW-W021": "OM-CONS-021",
    "OMW-W022": "OM-CONS-022",
    "OMW-W023": "OM-CONS-023",
    "OMW-W024": "OM-CONS-024",
    "OMW-W025": "OM-CONS-025",
    "OMW-W026": "OM-CONS-026",
    "OMW-W040": "OM-CONS-040",
    "OMI-I001": "OM-DD-030",
}
_SEVERITY: dict[str, Severity] = {"E": "error", "W": "warning", "I": "info"}
_NET_LEASE_TYPES = {"NN", "NNN", "absolute-net"}


@dataclass
class Tolerances:
    """Consistency tolerances (§H.4 [OM-ERR-002] — configurable)."""

    cap_rate_abs: float = 0.005  # absolute, since cap rate is itself a small fraction
    monetary_rel: float = 0.01  # relative, for money/PSF cross-checks
    rate_abs: float = 0.005  # absolute, for escalation-rate checks


@dataclass
class Report:
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    info: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no error-tier findings (i.e. embed would be allowed)."""
        return not self.errors


def _mk(
    code: str, path: str, message: str, *, expected: Any = None, actual: Any = None
) -> Finding:
    severity = _SEVERITY[code.split("-")[1][0]]
    return Finding(
        code, severity, path, message, expected=expected, actual=actual,
        requirement=_REQUIREMENT.get(code),
    )


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rel_off(actual: float, expected: float) -> float:
    return abs(actual - expected) / abs(expected) if expected else float("inf")


def _date(value: Any) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def validate(
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | None = None,
    tolerances: Tolerances | None = None,
) -> Report:
    report = Report()
    tol = tolerances or Tolerances()
    _error_tier(payload, schema, report)
    _warning_tier(payload, report, tol)
    _info_tier(payload, report)
    # Deterministic ordering (§H.1): stable across runs and implementations.
    report.errors.sort(key=lambda f: (f.code, f.path))
    report.warnings.sort(key=lambda f: (f.code, f.path))
    report.info.sort(key=lambda f: (f.code, f.path))
    return report


def _error_tier(
    payload: Mapping[str, Any], schema: Mapping[str, Any] | None, report: Report
) -> None:
    if schema is not None:
        # format_checker makes `format: date` etc. ASSERTED, not annotation-only — parity with
        # Track B's ajv-formats (mode: full). Without it a malformed assertedDate passes here
        # but fails in JS: a silent cross-impl fork ([OM-VAL-002]).
        validator = jsonschema.Draft202012Validator(
            dict(schema), format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        )
        for err in sorted(validator.iter_errors(dict(payload)), key=str):
            report.errors.append(_map_schema_error(err))
    else:
        _schema_free_checks(payload, report)


def _map_schema_error(err: jsonschema.ValidationError) -> Finding:
    """Map one jsonschema error to a stable §H code — path-based, matching Track B's mapError."""
    path = "/" + "/".join(str(p) for p in err.absolute_path)
    if path == "/meta/signature":
        return _mk("OMV-E003", "/meta/signature", "signature reserved in 0.1 (null/absent)")
    if err.validator == "required" and path == "/deal":
        missing = err.message.split("'")[1] if "'" in err.message else ""
        if missing in ("noiType", "noiAsOfDate"):
            return _mk("OMV-E002", f"/deal/{missing}", "noiType/noiAsOfDate required with noi")
    if path == "/meta/supersedes":
        return _mk("OMV-E010", "/meta/supersedes", "meta.supersedes must be sha256:<64hex>/null")
    return _mk("OMV-E001", path, err.message)


def _schema_free_checks(payload: Mapping[str, Any], report: Report) -> None:
    """The subset of error checks reproducible without a schema (schema=None path)."""
    deal = payload.get("deal") or {}
    if "noi" in deal and (deal.get("noiType") is None or deal.get("noiAsOfDate") is None):
        report.errors.append(_mk("OMV-E002", "/deal", "noi present without noiType/noiAsOfDate"))
    if (payload.get("meta") or {}).get("signature") is not None:
        report.errors.append(
            _mk("OMV-E003", "/meta/signature", "signature populated (reserved in 0.1)")
        )


def _warning_tier(payload: Mapping[str, Any], report: Report, tol: Tolerances) -> None:
    deal = payload.get("deal") or {}
    prop = payload.get("property") or {}
    lease = payload.get("lease") or {}
    warn = report.warnings.append

    cap = _num(deal.get("capRate"))
    noi = _num(deal.get("noi"))
    price = _num(deal.get("askingPrice"))
    building_sf = _num(prop.get("buildingSF"))

    # OMW-W010: cap rate vs NOI / price (absolute tolerance).
    if cap is not None and noi is not None and price:
        implied = noi / price
        if abs(cap - implied) > tol.cap_rate_abs:
            warn(_mk("OMW-W010", "/deal/capRate", "cap rate disagrees with NOI / askingPrice",
                     expected=round(implied, 4), actual=cap))

    # OMW-W011: price/SF vs askingPrice / buildingSF.
    pps = _num(deal.get("pricePerSF"))
    if pps is not None and price is not None and building_sf:
        implied = price / building_sf
        if _rel_off(pps, implied) > tol.monetary_rel:
            warn(_mk("OMW-W011", "/deal/pricePerSF",
                     "price/SF disagrees with askingPrice / buildingSF",
                     expected=round(implied, 2), actual=pps))

    # OMW-W040: net lease asserted but landlord bears pass-through costs (tenant should).
    lease_type = lease.get("leaseTypeAsserted")
    resp = lease.get("landlordResponsibilities") or {}
    if lease_type in _NET_LEASE_TYPES and any(resp.get(k) for k in ("taxes", "insurance", "cam")):
        warn(_mk("OMW-W040", "/lease/landlordResponsibilities",
                 f"{lease_type} lease but landlord bears taxes/insurance/cam"))

    schedule = lease.get("rentSchedule") or []
    if isinstance(schedule, list) and schedule:
        first_rent = _num((schedule[0] or {}).get("annualRent"))
        # OMW-W020: year-1 annual rent vs stated (in-place) NOI.
        if first_rent is not None and noi is not None and deal.get("noiType") == "in-place":
            if _rel_off(first_rent, noi) > tol.monetary_rel:
                warn(_mk("OMW-W020", "/lease/rentSchedule/0/annualRent",
                         "year-1 annual rent disagrees with stated in-place NOI",
                         expected=noi, actual=first_rent))
        _rent_schedule_checks(schedule, building_sf, lease, tol, warn)


def _rent_schedule_checks(
    schedule: list[Any], building_sf: float | None, lease: Mapping[str, Any],
    tol: Tolerances, warn: Any,
) -> None:
    commencement = _date(lease.get("commencement"))
    expiration = _date(lease.get("expiration"))
    for i, raw in enumerate(schedule):
        period = raw or {}
        annual = _num(period.get("annualRent"))
        rent_psf = _num(period.get("rentPSF"))
        monthly = _num(period.get("monthlyRent"))
        base = f"/lease/rentSchedule/{i}"

        # OMW-W024: rentPSF vs annualRent / buildingSF.
        if rent_psf is not None and annual is not None and building_sf:
            implied = annual / building_sf
            if _rel_off(rent_psf, implied) > tol.monetary_rel:
                warn(_mk("OMW-W024", f"{base}/rentPSF",
                         "rentPSF disagrees with annualRent / buildingSF",
                         expected=round(implied, 2), actual=rent_psf))

        # OMW-W025: monthlyRent vs annualRent / 12.
        if monthly is not None and annual is not None:
            if _rel_off(monthly, annual / 12) > tol.monetary_rel:
                warn(_mk("OMW-W025", f"{base}/monthlyRent",
                         "monthlyRent disagrees with annualRent / 12",
                         expected=round(annual / 12, 2), actual=monthly))

        # OMW-W014: non-positive rent with no abatement flag.
        if annual is not None and annual <= 0 and period.get("abatement") is None:
            warn(_mk("OMW-W014", f"{base}/annualRent",
                     "non-positive annualRent without an abatement", actual=annual))

        # OMW-W026: rent period falls outside the lease term.
        p_start, p_end = _date(period.get("periodStart")), _date(period.get("periodEnd"))
        if commencement and p_start and p_start < commencement:
            warn(_mk("OMW-W026", f"{base}/periodStart",
                     "rent period starts before lease commencement"))
        if expiration and p_end and p_end > expiration:
            warn(_mk("OMW-W026", f"{base}/periodEnd",
                     "rent period ends after lease expiration"))

        if i == 0:
            continue
        prior = schedule[i - 1] or {}
        prev_end = _date(prior.get("periodEnd"))
        start = p_start
        # OMW-W023: escalationFromPrior vs the actual step in annualRent.
        esc = _num(period.get("escalationFromPrior"))
        prev_annual = _num(prior.get("annualRent"))
        if esc is not None and prev_annual and annual is not None:
            implied_step = annual / prev_annual - 1
            if abs(esc - implied_step) > tol.rate_abs:
                warn(_mk("OMW-W023", f"{base}/escalationFromPrior",
                         "escalationFromPrior disagrees with the annualRent step",
                         expected=round(implied_step, 4), actual=esc))

        if prev_end is None or start is None:
            continue
        # OMW-W022 overlap / OMW-W021 gap between consecutive periods.
        if start <= prev_end:
            warn(_mk("OMW-W022", f"{base}/periodStart",
                     "rent-schedule period overlaps the previous period"))
        elif (start - prev_end).days > 1:
            warn(_mk("OMW-W021", f"{base}/periodStart",
                     "gap between consecutive rent-schedule periods"))


def _info_tier(payload: Mapping[str, Any], report: Report) -> None:
    deal = payload.get("deal") or {}
    # OMI-I001: pro-forma NOI is forward-looking context, not an in-place figure.
    if deal.get("noiType") == "pro-forma":
        report.info.append(
            _mk("OMI-I001", "/deal/noiType", "NOI is pro-forma (forward-looking), not in-place")
        )
