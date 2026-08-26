# SPDX-License-Identifier: MIT
"""Two-tier payload validation (spec §H): schema errors block, consistency warnings never do.

Errors (``OMV-E###``) come from JSON Schema plus the noi/signature rules; warnings
(``OMW-W###``) are internal-consistency checks against configurable tolerances (§H.4
[OM-ERR-014]); info (``OMI-I###``) is advisory context. Warnings/info NEVER block and MUST NOT
mutate the payload. Tooling checks internal consistency only - market truth is out of scope
forever. Every finding carries a requirement back-reference (§H.1) and findings are emitted in
deterministic (code, path) order.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from .canonical import MAX_SAFE_INT, payload_hash
from .errors import Finding, Severity
from .schema import load_schema

# Requirement back-references (§H.1) keyed by finding code.
_REQUIREMENT = {
    "OMV-E001": "OM-DD-001",
    "OMV-E002": "OM-DD-003",
    "OMV-E003": "OM-ERR-090",
    "OMV-E010": "OM-ERR-013",
    "OMV-E011": "OM-CANON-013",  # integer out of the ECMAScript safe range - embed would reject it
    "OMW-W010": "OM-CONS-010",
    "OMW-W011": "OM-CONS-011",
    "OMW-W012": "OM-CONS-012",
    "OMW-W013": "OM-CONS-013",
    "OMW-W014": "OM-CONS-014",
    "OMW-W020": "OM-CONS-020",
    "OMW-W021": "OM-CONS-021",
    "OMW-W022": "OM-CONS-022",
    "OMW-W023": "OM-CONS-023",
    "OMW-W024": "OM-CONS-024",
    "OMW-W025": "OM-CONS-025",
    "OMW-W026": "OM-CONS-026",
    "OMW-W030": "OM-CONS-030",
    "OMW-W031": "OM-CONS-031",
    "OMW-W032": "OM-CONS-032",
    "OMW-W033": "OM-CONS-033",
    "OMW-W034": "OM-CONS-034",
    "OMW-W040": "OM-CONS-040",
    "OMW-W041": "OM-CONS-041",
    "OMW-W050": "OM-CONS-050",
    "OMW-W051": "OM-TRUST-009",  # stale/superseded (mirror carries a newer assertion)
    "OMW-W052": "OM-TRUST-010",  # diverged (same-domain mirror shows different, non-superseding)
    "OMW-W060": "OM-CONS-060",
    "OMW-W061": "OM-DD-002",
    "OMI-I001": "OM-DD-002",
    "OMI-I002": "OM-DD-004",
    "OMI-I003": "OM-ERR-014",
}
_SIG_MSG = "signature must be null or the reserved {alg,keyId,value} shape"  # #117
_DAYS_PER_MONTH = 30.4375  # 365.25 / 12, for month↔day term arithmetic
_SEVERITY: dict[str, Severity] = {"E": "error", "W": "warning", "I": "info"}
_NET_LEASE_TYPES = {"NN", "NNN", "absolute-net"}
_GROSS_LEASE_TYPES = {"gross", "modified-gross"}
_ALL_RESP = ("roof", "structure", "parking", "hvac", "taxes", "insurance", "cam")
_STRUCTURAL_RESP = ("roof", "structure", "parking", "hvac")


@dataclass
class Tolerances:
    """Consistency tolerances (§H.4 [OM-ERR-002] - configurable)."""

    cap_rate_abs: float = 0.005  # absolute, since cap rate is itself a small fraction
    monetary_rel: float = 0.01  # relative, for money/PSF cross-checks
    rate_abs: float = 0.005  # absolute, for escalation-rate checks
    remaining_term_days: float = 31.0  # §H.4 tol.remainingTermDays (OMW-W030)
    lease_term_days: float = 31.0  # §H.4 tol.leaseTermDays (OMW-W031)
    cap_rate_band: tuple[float, float] = (0.02, 0.20)  # §H.4 tol.capRateBand (OMW-W013)


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


def _obj(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return payload[key] iff it is a JSON object, else {}. A truthy NON-object (a str/list/number
    where an object is expected) is a schema error the error tier already reports; the consistency
    tiers must not then crash dereferencing it (`.get()` on a str). Mirrors the JS isObject guard so
    a schema-invalid nested field degrades to a schema error on BOTH cores instead of a Python-only
    AttributeError - closing a Python<->JS outcome fork."""
    v = payload.get(key)
    return v if isinstance(v, Mapping) else {}


def _num(value: object) -> float | None:
    # `object` not `Any` (#153): callers must narrow, and the isinstance gate is the only entry.
    # A non-finite (NaN/Infinity) value is treated as absent so the consistency tier never computes
    # or reports a non-finite expected/actual - it's already an error (OMV-E011) and can't be cross-
    # checked meaningfully; it also keeps every emitted finding JSON-serializable (allow_nan=False).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        f = float(value)
        return f if math.isfinite(f) else None
    return None


def _rel_off(actual: float, expected: float) -> float:
    return abs(actual - expected) / abs(expected) if expected else float("inf")


def _date(value: object) -> dt.date | None:  # #153: object, narrowed below
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
    as_of: str | None = None,
) -> Report:
    # [Ma2] Default to the bundled 0.1 schema so the ergonomic `validate(payload)` performs FULL
    # schema validation. The old default (schema=None -> a two-rule subset) silently skipped every
    # structural/type/required/format error and could report ok=True on a schema-invalid payload.
    if schema is None:
        schema = load_schema()
    report = Report()
    tol = tolerances or Tolerances()
    # [Mi3/Mi6] A non-object payload is a schema violation, not a crash: run only the schema
    # tier (OMV-E001 for the wrong type) and skip the consistency/info tiers that need a mapping -
    # mirrors the JS validatePayload guard. Prevents an AttributeError / miscoded IO error.
    if not isinstance(payload, Mapping):
        _error_tier(payload, schema, report)
        report.errors[:] = _dedupe_ancestor_errors(report.errors)
        report.errors.sort(key=lambda f: (f.code, f.path))
        return report
    # Reference date for term checks (OMW-W030): explicit as_of, else the payload's assertedDate,
    # so the check is internal-consistency (§H.6) and deterministic rather than wall-clock.
    # processing_date is the wall-clock-free "now" for OMW-W032 - set ONLY when a caller passes
    # as_of; a validator never reads the system clock, so W032 is silent on the default path.
    processing_date = _date(as_of) if as_of else None
    as_of_date = processing_date if processing_date else _date(payload.get("assertedDate"))
    _error_tier(payload, schema, report)
    _number_range_tier(payload, report)
    report.errors[:] = _dedupe_ancestor_errors(report.errors)
    _warning_tier(payload, report, tol, as_of_date, processing_date)
    _info_tier(payload, report)
    # Deterministic ordering (§H.1): stable across runs and implementations.
    report.errors.sort(key=lambda f: (f.code, f.path))
    report.warnings.sort(key=lambda f: (f.code, f.path))
    report.info.sort(key=lambda f: (f.code, f.path))
    return report


# Compiled-validator cache (#148): building a Draft202012Validator resolves the 2020-12 meta-schema
# each time - the dominant cost of a hosted om_validate/om_embed. Callers pass the same schema
# object (openom_core.schema.load_schema), so keying by id() gives a hot-path hit; a fresh dict
# (tests) simply misses. Bounded so distinct schemas can't grow it unbounded.
_VALIDATOR_CACHE: OrderedDict[int, jsonschema.Draft202012Validator] = OrderedDict()
_VALIDATOR_CACHE_MAX = 8


def _validator_for(schema: Mapping[str, Any]) -> jsonschema.Draft202012Validator:
    key = id(schema)
    cached = _VALIDATOR_CACHE.get(key)
    if cached is not None:
        _VALIDATOR_CACHE.move_to_end(key)
        return cached
    # format_checker makes `format: date` etc. ASSERTED, not annotation-only - parity with Track B's
    # ajv-formats (mode: full). Without it a malformed assertedDate passes here but fails in JS
    # ([OM-VAL-002]).
    validator = jsonschema.Draft202012Validator(
        dict(schema), format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    _VALIDATOR_CACHE[key] = validator
    if len(_VALIDATOR_CACHE) > _VALIDATOR_CACHE_MAX:
        _VALIDATOR_CACHE.popitem(last=False)
    return validator


def _error_tier(payload: Any, schema: Mapping[str, Any], report: Report) -> None:
    # Pass the payload as-is (not dict(payload)): jsonschema validates any JSON value, and a
    # non-object payload must hit the type check as OMV-E001 rather than raising in dict() [Mi3].
    validator = _validator_for(schema)
    for err in sorted(validator.iter_errors(payload), key=str):
        report.errors.append(_map_schema_error(err))


def _number_range_tier(payload: Mapping[str, Any], report: Report) -> None:
    """Reject numbers outside the ECMAScript safe-integer range at validate time, so validate and
    embed AGREE. The schema permits any integer, but canonicalization (OM-CANON-013) refuses an
    integer-valued number with |v| > 2^53-1 - it would be silently rounded under the JS number
    model. Without this a broker gets a green validate and then a failed embed; here it is caught at
    the review gate. Same thresholds as canonical (2^53-1 magnitude AND finiteness), so the two
    stages can never drift - a non-finite (NaN/Infinity) leaf is rejected here exactly as embed's
    canonicalization rejects it."""
    for path, value in _iter_numbers(payload, ""):
        if isinstance(value, bool):
            continue
        if isinstance(value, float) and not math.isfinite(value):
            report.errors.append(_mk("OMV-E011", path, f"non-finite number: {value}"))
            continue
        unsafe_int = isinstance(value, int) and abs(value) > MAX_SAFE_INT
        unsafe_float = isinstance(value, float) and value.is_integer() and abs(value) > MAX_SAFE_INT
        if unsafe_int or unsafe_float:
            report.errors.append(
                _mk("OMV-E011", path, f"integer exceeds the safe range (2^53-1): {value}")
            )


def _iter_numbers(node: Any, path: str) -> Iterator[tuple[str, int | float]]:
    """Yield (json-pointer, number) for every numeric leaf, depth-first (booleans included; the
    caller filters them). Path style matches _map_schema_error (unescaped '/'-joined tokens)."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield from _iter_numbers(value, f"{path}/{key}")
    elif isinstance(node, (list, tuple)):
        for idx, value in enumerate(node):
            yield from _iter_numbers(value, f"{path}/{idx}")
    elif isinstance(node, (int, float)):
        yield path, node


def _map_schema_error(err: jsonschema.ValidationError) -> Finding:
    """Map one jsonschema error to a stable §H code - path-based, matching Track B's mapError."""
    # RFC 6901: the whole document is the empty string "", not "/" - match the JS core + spec
    # OM-ERR-008 so a document-level error reports the same path on both cores.
    parts = list(err.absolute_path)
    path = "/" + "/".join(str(p) for p in parts) if parts else ""
    if err.validator == "required":
        # Point a missing-required error at the MISSING CHILD (RFC 6901), like ajv - jsonschema
        # attaches it to the container path, which forks the finding list from the JS core.
        missing = err.message.split("'")[1] if "'" in err.message else ""
        child = f"{path}/{missing}" if missing else path
        if missing in ("noiType", "noiAsOfDate"):
            return _mk("OMV-E002", child, "noiType/noiAsOfDate required with noi")
        return _mk("OMV-E001", child, err.message)
    if path.startswith("/meta/signature"):
        # #117: null OR the reserved {alg,keyId,value} shape; anything else is OMV-E003.
        return _mk("OMV-E003", "/meta/signature", _SIG_MSG)
    if path == "/meta/supersedes":
        return _mk("OMV-E010", "/meta/supersedes", "meta.supersedes must be sha256:<64hex>/null")
    return _mk("OMV-E001", path, err.message)


def _is_ancestor(a: str, b: str) -> bool:
    """True if path `a` is a STRICT ancestor of path `b` (RFC 6901). Root "" is an ancestor of any
    non-empty path; otherwise `b` must extend `a` at a segment boundary."""
    if a == b:
        return False
    return a == "" or b.startswith(a + "/")


def _dedupe_ancestor_errors(errors: list[Finding]) -> list[Finding]:
    """Drop a generic OMV-E001 whose path is a strict ancestor of another error's path: when a
    specific error exists deeper (e.g. /deal/capRate, or /deal/noiType), the bubbled-up parent
    (/deal) and root ("") OMV-E001 are redundant noise. This shared normal form makes the
    Python and JS error lists agree - both validators otherwise surface different ancestor subsets.
    A specific code (E002/E003/E010/E011) is never dropped; the root "" survives iff it is alone."""
    paths = [f.path for f in errors]
    return [
        f
        for f in errors
        if not (f.code == "OMV-E001" and any(_is_ancestor(f.path, other) for other in paths))
    ]


def _warning_tier(
    payload: Mapping[str, Any], report: Report, tol: Tolerances,
    as_of_date: dt.date | None = None, processing_date: dt.date | None = None,
) -> None:
    deal = _obj(payload, "deal")
    prop = _obj(payload, "property")
    lease = _obj(payload, "lease")
    warn = report.warnings.append
    _date_term_checks(lease, as_of_date, tol, warn)
    _date_sanity_checks(payload, deal, lease, processing_date, warn)
    _self_supersede_check(payload, warn)

    # OMW-W061 (#119): currency absent on an EXPLICITLY non-US property - the silent-USD default is
    # likely wrong. The plain-absent case stays info (OMI-I001); this targets the real footgun and
    # skips the common US omission. (currency becomes REQUIRED next major.)
    if payload.get("currency") is None:
        country = (prop.get("address") or {}).get("addressCountry")
        if isinstance(country, str) and country.upper() not in ("US", ""):
            warn(_mk("OMW-W061", "/currency",
                     "currency absent on a non-US property; assumed USD - confirm the currency"))

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

    # OMW-W013: cap rate outside the plausibility band (§H.4 tol.capRateBand).
    if cap is not None:
        lo, hi = tol.cap_rate_band
        if not lo <= cap <= hi:
            warn(_mk("OMW-W013", "/deal/capRate",
                     f"capRate outside the plausibility band [{lo}, {hi}]", actual=cap))

    # OMW-W014: askingPrice, noi, or buildingSF is non-positive (§H.3).
    for value, path, label in (
        (price, "/deal/askingPrice", "askingPrice"),
        (noi, "/deal/noi", "noi"),
        (building_sf, "/property/buildingSF", "buildingSF"),
    ):
        if value is not None and value <= 0:
            warn(_mk("OMW-W014", path, f"{label} is non-positive", actual=value))

    # OMW-W012: pro-forma NOI presented without noiAsOfDate context.
    if deal.get("noiType") == "pro-forma" and not deal.get("noiAsOfDate"):
        warn(_mk("OMW-W012", "/deal/noiAsOfDate",
                 "pro-forma NOI presented without noiAsOfDate context"))

    # OMW-W040: net lease asserted but landlord bears pass-through costs (tenant should).
    lease_type = lease.get("leaseTypeAsserted")
    resp = lease.get("landlordResponsibilities") or {}
    if lease_type in _NET_LEASE_TYPES and any(resp.get(k) for k in ("taxes", "insurance", "cam")):
        warn(_mk("OMW-W040", "/lease/landlordResponsibilities",
                 f"{lease_type} lease but landlord bears taxes/insurance/cam"))

    # OMW-W041: leaseTypeAsserted contradicts the responsibility set generally (§H.3).
    if lease_type in _GROSS_LEASE_TYPES and resp and not any(resp.get(k) for k in _ALL_RESP):
        warn(_mk("OMW-W041", "/lease/landlordResponsibilities",
                 f"{lease_type} lease but landlord bears no responsibilities"))
    elif lease_type == "absolute-net" and any(resp.get(k) for k in _STRUCTURAL_RESP):
        warn(_mk("OMW-W041", "/lease/landlordResponsibilities",
                 "absolute-net lease but landlord bears structural/HVAC responsibilities"))

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


def _date_term_checks(
    lease: Mapping[str, Any],
    as_of_date: dt.date | None,
    tol: Tolerances,
    warn: Callable[[Finding], None],
) -> None:
    """OMW-W030/W031: stated term fields vs the date arithmetic (§H.4)."""
    commencement = _date(lease.get("commencement"))
    expiration = _date(lease.get("expiration"))
    term_months = _num(lease.get("termMonths"))
    remaining_months = _num(lease.get("remainingTermMonths"))

    # OMW-W031: stated total term vs (expiration − commencement).
    if term_months is not None and commencement and expiration:
        actual_days = (expiration - commencement).days
        if abs(actual_days - term_months * _DAYS_PER_MONTH) > tol.lease_term_days:
            warn(_mk("OMW-W031", "/lease/termMonths",
                     "stated lease term disagrees with expiration - commencement",
                     expected=round(actual_days / _DAYS_PER_MONTH, 1), actual=term_months))

    # OMW-W030: stated remaining term vs (expiration − as_of).
    if remaining_months is not None and expiration and as_of_date:
        actual_days = (expiration - as_of_date).days
        if abs(actual_days - remaining_months * _DAYS_PER_MONTH) > tol.remaining_term_days:
            warn(_mk("OMW-W030", "/lease/remainingTermMonths",
                     "stated remaining term disagrees with expiration - as_of",
                     expected=round(actual_days / _DAYS_PER_MONTH, 1), actual=remaining_months))


def _date_sanity_checks(
    payload: Mapping[str, Any], deal: Mapping[str, Any], lease: Mapping[str, Any],
    processing_date: dt.date | None, warn: Callable[[Finding], None],
) -> None:
    """OMW-W032/W033/W034: date-ordering sanity (§H.3)."""
    asserted = _date(payload.get("assertedDate"))
    noi_as_of = _date(deal.get("noiAsOfDate"))
    commencement = _date(lease.get("commencement"))
    expiration = _date(lease.get("expiration"))

    # OMW-W032: assertedDate in the future relative to the processing date (caller-supplied only).
    if processing_date and asserted and asserted > processing_date:
        warn(_mk("OMW-W032", "/assertedDate",
                 "assertedDate is in the future relative to the processing date",
                 expected=processing_date.isoformat(), actual=asserted.isoformat()))

    # OMW-W033: noiAsOfDate after assertedDate (an as-of newer than the assertion itself).
    if noi_as_of and asserted and noi_as_of > asserted:
        warn(_mk("OMW-W033", "/deal/noiAsOfDate", "noiAsOfDate is after assertedDate",
                 expected=asserted.isoformat(), actual=noi_as_of.isoformat()))

    # OMW-W034: lease expiration on or before commencement.
    if commencement and expiration and expiration <= commencement:
        warn(_mk("OMW-W034", "/lease/expiration",
                 "lease expiration is on or before commencement", actual=expiration.isoformat()))


def _self_supersede_check(payload: Mapping[str, Any], warn: Callable[[Finding], None]) -> None:
    """OMW-W050: self-supersede (§H.3).

    The integrity hash covers ``meta.supersedes`` itself, so ``supersedes == hash(full payload)``
    is an unreachable fixpoint. The meaningful, deterministic reading is: ``supersedes`` equals
    the hash of *this* payload with the ``supersedes`` pointer removed - i.e. the payload
    supersedes content byte-identical to itself (a no-op re-embed).
    """
    meta = _obj(payload, "meta")
    supersedes = meta.get("supersedes")
    if not isinstance(supersedes, str):
        return
    stripped = {k: (dict(v) if k == "meta" else v) for k, v in payload.items()}
    stripped["meta"] = {k: v for k, v in meta.items() if k != "supersedes"}
    try:
        own = payload_hash(stripped)
    except (ValueError, TypeError):  # hashing must never break validation
        return
    if supersedes == own:
        warn(_mk("OMW-W050", "/meta/supersedes",
                 "meta.supersedes equals this payload's own hash minus the pointer"))


def _rent_schedule_checks(
    schedule: list[Any], building_sf: float | None, lease: Mapping[str, Any],
    tol: Tolerances, warn: Callable[[Finding], None],
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

        # OMW-W060: source asserted as 'verified' but 0.1 carries no corroborating metadata.
        if period.get("source") == "verified":
            warn(_mk("OMW-W060", f"{base}/source",
                     "source is 'verified' but no corroborating verification metadata is present"))

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
    deal = _obj(payload, "deal")
    prop = _obj(payload, "property")
    lease = _obj(payload, "lease")
    info = report.info.append
    schedule = lease.get("rentSchedule") or []
    periods = [p for p in schedule if isinstance(p, Mapping)] if isinstance(schedule, list) else []

    # OMI-I001: currency absent -> assumed USD (OM-DD-002 default).
    if payload.get("currency") is None:
        info(_mk("OMI-I001", "/currency", "currency absent; assumed USD (OM-DD-002 default)"))

    # OMI-I002: a rentPeriod source tag was absent -> assumed 'asserted' (OM-DD-004).
    if any(p.get("source") is None for p in periods):
        info(_mk("OMI-I002", "/lease/rentSchedule",
                 "a rentPeriod source tag was absent; assumed 'asserted' (OM-DD-004)"))

    # OMI-I003: a cross-check was skipped because required inputs were absent (§H.4).
    building_sf = _num(prop.get("buildingSF"))
    if _num(deal.get("capRate")) is not None and (
        _num(deal.get("noi")) is None or _num(deal.get("askingPrice")) is None
    ):
        info(_mk("OMI-I003", "/deal/capRate",
                 "cap-rate cross-check (OMW-W010) skipped: noi or askingPrice absent"))
    if _num(deal.get("pricePerSF")) is not None and (
        _num(deal.get("askingPrice")) is None or building_sf is None
    ):
        info(_mk("OMI-I003", "/deal/pricePerSF",
                 "price/SF cross-check (OMW-W011) skipped: askingPrice or buildingSF absent"))
    if building_sf is None and any(_num(p.get("rentPSF")) is not None for p in periods):
        info(_mk("OMI-I003", "/lease/rentSchedule",
                 "rentPSF cross-check (OMW-W024) skipped: buildingSF absent"))
