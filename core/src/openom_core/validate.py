# SPDX-License-Identifier: MIT
"""Two-tier payload validation (spec §H): schema errors block, consistency warnings never do.

Errors (``OMV-E###``) come from JSON Schema plus the noi/signature rules; warnings
(``OMW-W###``) are internal-consistency checks against the tolerances of §H.4 [OM-ERR-014].
Warnings are advisory and MUST NOT mutate the payload. Market truth is out of scope forever.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from .errors import Finding

# §H.4 [OM-ERR-014] default tolerances.
CAP_RATE_ABS = 0.005
MONETARY_REL = 0.01


@dataclass
class Report:
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    info: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no error-tier findings (i.e. embed would be allowed)."""
        return not self.errors


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


def validate(payload: Mapping[str, Any], *, schema: Mapping[str, Any] | None = None) -> Report:
    report = Report()
    _error_tier(payload, schema, report)
    _warning_tier(payload, report)
    return report


def _error_tier(
    payload: Mapping[str, Any], schema: Mapping[str, Any] | None, report: Report
) -> None:
    if schema is not None:
        # format_checker makes `format: date` etc. ASSERTED, not annotation-only — parity with
        # Track B's ajv-formats (mode: full). Without it, a malformed assertedDate passes here
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
        return Finding(
            "OMV-E003", "error", "/meta/signature", "signature reserved in 0.1 (null/absent)"
        )
    if err.validator == "required" and path == "/deal":
        missing = err.message.split("'")[1] if "'" in err.message else ""
        if missing in ("noiType", "noiAsOfDate"):
            return Finding(
                "OMV-E002", "error", f"/deal/{missing}", "noiType/noiAsOfDate required with noi"
            )
    if path == "/meta/supersedes":
        return Finding(
            "OMV-E010", "error", "/meta/supersedes", "meta.supersedes must be sha256:<64hex>/null"
        )
    return Finding("OMV-E001", "error", path, err.message)


def _schema_free_checks(payload: Mapping[str, Any], report: Report) -> None:
    """The subset of error checks reproducible without a schema (schema=None path)."""
    deal = payload.get("deal") or {}
    if "noi" in deal and (deal.get("noiType") is None or deal.get("noiAsOfDate") is None):
        report.errors.append(
            Finding("OMV-E002", "error", "/deal", "noi present without noiType/noiAsOfDate")
        )
    signature = (payload.get("meta") or {}).get("signature")
    if signature is not None:
        report.errors.append(
            Finding("OMV-E003", "error", "/meta/signature", "signature populated (reserved in 0.1)")
        )


def _warning_tier(payload: Mapping[str, Any], report: Report) -> None:
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
        if abs(cap - implied) > CAP_RATE_ABS:
            warn(Finding("OMW-W010", "warning", "/deal/capRate",
                         "cap rate disagrees with NOI / askingPrice", expected=round(implied, 4),
                         actual=cap))

    # OMW-W011: price/SF vs askingPrice / buildingSF.
    pps = _num(deal.get("pricePerSF"))
    if pps is not None and price is not None and building_sf:
        implied = price / building_sf
        if _rel_off(pps, implied) > MONETARY_REL:
            warn(Finding("OMW-W011", "warning", "/deal/pricePerSF",
                         "price/SF disagrees with askingPrice / buildingSF",
                         expected=round(implied, 2), actual=pps))

    schedule = lease.get("rentSchedule") or []
    if isinstance(schedule, list) and schedule:
        first_rent = _num((schedule[0] or {}).get("annualRent"))
        # OMW-W020: year-1 annual rent vs stated (in-place) NOI.
        if first_rent is not None and noi is not None and deal.get("noiType") == "in-place":
            if _rel_off(first_rent, noi) > MONETARY_REL:
                warn(Finding("OMW-W020", "warning", "/lease/rentSchedule/0/annualRent",
                             "year-1 annual rent disagrees with stated in-place NOI",
                             expected=noi, actual=first_rent))
        _rent_schedule_checks(schedule, building_sf, warn)


def _rent_schedule_checks(schedule: list[Any], building_sf: float | None, warn: Any) -> None:
    for i, period in enumerate(schedule):
        period = period or {}
        # OMW-W024: rentPSF vs annualRent / buildingSF.
        rent_psf, annual = _num(period.get("rentPSF")), _num(period.get("annualRent"))
        if rent_psf is not None and annual is not None and building_sf:
            implied = annual / building_sf
            if _rel_off(rent_psf, implied) > MONETARY_REL:
                warn(Finding("OMW-W024", "warning", f"/lease/rentSchedule/{i}/rentPSF",
                             "rentPSF disagrees with annualRent / buildingSF",
                             expected=round(implied, 2), actual=rent_psf))
        if i == 0:
            continue
        prev_end = _date((schedule[i - 1] or {}).get("periodEnd"))
        start = _date(period.get("periodStart"))
        if prev_end is None or start is None:
            continue
        # OMW-W022 overlap: next period starts on/before the prior period's end.
        if start <= prev_end:
            warn(Finding("OMW-W022", "warning", f"/lease/rentSchedule/{i}/periodStart",
                         "rent-schedule period overlaps the previous period"))
        # OMW-W021 gap: a hole between consecutive periods (> 1 day).
        elif (start - prev_end).days > 1:
            warn(Finding("OMW-W021", "warning", f"/lease/rentSchedule/{i}/periodStart",
                         "gap between consecutive rent-schedule periods"))
