# SPDX-License-Identifier: MIT
"""Deterministic Buildout listing -> openOM payload mapper (the connector->manifest bridge).

Grounded in the REAL Buildout `get_listing` shape (nested ``core.research_property_attributes.*`` +
``custom_fields.*`` + ``financials``). Pure + zero-inference: it normalizes names/units and omits
anything absent - it never guesses. The human/CLI supplies the assertion identity (assertedBy,
assertedDate, noiType, noiAsOfDate); those are never inferred from Buildout. The output is a schema-
valid openOM payload ready for ``om embed-batch``.

Note the two cap rates: ``cap_rate`` is Buildout's stated "Average CAP Rate" over the term (often
absent); ``cap_rate_derived`` is current NOI/price. We map the derived one because it is what the
openOM consistency check (NOI/price vs capRate) expects and what the OM's headline cap reflects.
"""

from __future__ import annotations

import math
from typing import Any

NS = "https://openom.app/ns/0.1"


def _num(v: Any) -> float | None:
    try:
        n = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    # A non-finite cell (1e400 / inf / nan) is omitted, not propagated - mirrors the JS connector's
    # Number.isFinite guard and stops _int() raising OverflowError (which aborted the batch).
    return n if math.isfinite(n) else None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _pct_to_fraction(v: Any) -> float | None:
    n = _num(v)
    return round(n / 100, 6) if n is not None else None


def _iso_date(mdy: Any) -> str | None:
    """'10/1/2026' -> '2026-10-01'. Returns None if not an M/D/Y date."""
    if not mdy:
        return None
    parts = str(mdy).strip().split("/")
    if len(parts) != 3:
        return None
    try:
        m, d, y = (int(p) for p in parts)
    except ValueError:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31 and y > 1900):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def _state_code(v: Any) -> str | None:
    """'GA - Georgia' -> 'GA'; 'GA' -> 'GA'."""
    if not v:
        return None
    head = str(v).split("-")[0].strip()
    return head.upper() if len(head) == 2 else None


def _lease_type(v: Any) -> str | None:
    """Map Buildout's free-text lease type to the openOM asserted value."""
    if not v:
        return None
    s = str(v).upper()
    if "NNN" in s:
        return "NNN"
    if "NN" in s:
        return "NN"
    if "GROSS" in s:
        return "gross"
    return str(v)


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    # drop absent values, incl. empty strings (schema forbids ""), but keep 0/0.0/False
    return {k: v for k, v in d.items() if v not in (None, "", {}, [])}


def _months_between(start_iso: str | None, end_iso: str | None) -> int | None:
    """Whole months between two ISO (YYYY-MM-DD) dates, or None. Deterministic (no clock)."""
    if not start_iso or not end_iso:
        return None
    try:
        sy, sm, sd = (int(x) for x in start_iso.split("-"))
        ey, em, ed = (int(x) for x in end_iso.split("-"))
    except ValueError:
        return None
    months = (ey - sy) * 12 + (em - sm)
    if ed < sd:  # a partial trailing month doesn't count
        months -= 1
    return months if months >= 0 else None


# Canonical fields tracked for a back-catalog coverage report (the numbers a buyer underwrites).
# Used to flag near-empty payloads before a bulk embed (Rule 6: review at scale).
_COVERAGE_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("askingPrice", ("deal", "askingPrice")),
    ("capRate", ("deal", "capRate")),
    ("noi", ("deal", "noi")),
    ("address", ("property", "address")),
    ("buildingSF", ("property", "buildingSF")),
    ("tenant", ("lease", "tenantEntity")),
    ("leaseType", ("lease", "leaseTypeAsserted")),
    ("expiration", ("lease", "expiration")),
)


def payload_coverage(payload: dict[str, Any]) -> dict[str, Any]:
    """Which tracked fields a mapped payload actually carries - for a pre-embed coverage report."""
    present: list[str] = []
    missing: list[str] = []
    for name, path in _COVERAGE_FIELDS:
        cur: Any = payload
        for seg in path:
            cur = cur.get(seg) if isinstance(cur, dict) else None
        (present if cur not in (None, "", {}, []) else missing).append(name)
    return {
        "filled": len(present), "of": len(_COVERAGE_FIELDS),
        "present": present, "missing": missing,
    }


def listing_to_payload(
    listing: dict[str, Any],
    *,
    asserted_by: dict[str, str],
    asserted_date: str,
    noi_type: str,
    noi_as_of: str | None = None,
) -> dict[str, Any]:
    """Map one Buildout ``get_listing`` object to a schema-valid openOM payload (partial fields only
    where Buildout has them). ``asserted_by``/``asserted_date``/``noi_type``/``noi_as_of`` are the
    human's assertion identity and are stamped verbatim, never inferred."""
    core: dict[str, Any] = listing.get("core", {})
    cf: dict[str, Any] = listing.get("custom_fields", {})
    fin: dict[str, Any] = listing.get("financials", {})

    def rp(attr: str) -> Any:
        return core.get(f"research_property_attributes.{attr}")

    address = _compact({
        "streetAddress": rp("address"),
        "addressLocality": rp("city"),
        "addressRegion": _state_code(rp("state")),
        "postalCode": rp("zip"),
        "addressCountry": "US" if str(rp("country_id")) == "1" else None,
    })
    lat, lng = _num(rp("latitude")), _num(rp("longitude"))
    geo = {"latitude": lat, "longitude": lng} if lat is not None and lng is not None else None
    lot = _num(rp("lot_size")) if str(rp("lot_size_units")).lower().startswith("acre") else None
    building_sf = _int(rp("building_size"))
    units = _int(rp("number_of_units"))
    # propertyType ([M4]): the primary asset-class filter, trivially mappable and never auto-filled
    # before. Buildout exposes it as a research attribute; omitted (never guessed) when absent.
    prop_type = rp("property_type") or rp("property_sub_type") or cf.get("Property type")
    property_ = _compact({
        "propertyType": str(prop_type).strip().lower() if prop_type else None,
        "address": address or None,
        "geo": geo,
        "buildingSF": building_sf,
        "yearBuilt": _int(rp("year_built")),
        "lotAcres": lot,
        "units": units,
        "occupancy": _pct_to_fraction(rp("occupancy_pct")),
    })

    price = _int(fin.get("sale_price"))
    deal = _compact({
        "askingPrice": price,
        "capRate": _pct_to_fraction(fin.get("cap_rate_derived") or fin.get("cap_rate")),
        "noi": _int(fin.get("noi") or cf.get("NOI")),
        # Deterministically derived from mapped values ([M4]); not in Buildout, computed here.
        "pricePerUnit": round(price / units) if price and units else None,
        "pricePerSF": round(price / building_sf, 2) if price and building_sf else None,
        "noiType": noi_type,
        "noiAsOfDate": noi_as_of or asserted_date,
        "status": "active",
    })

    commencement = _iso_date(cf.get("Lease start date"))
    expiration = _iso_date(cf.get("Lease expiration date"))
    guarantor_name = cf.get("Lease guarantor")
    lease = _compact({
        "tenantEntity": cf.get("Tenant"),
        "leaseTypeAsserted": _lease_type(cf.get("Lease type")),
        "commencement": commencement,
        "expiration": expiration,
        # termMonths ([M4]): derived from the two dates above, deterministic (no clock).
        "termMonths": _months_between(commencement, expiration),
        "guarantor": {"name": guarantor_name, "type": "corporate"} if guarantor_name else None,
    })

    return _compact({
        "@context": ["https://schema.org", NS],
        "@type": "RealEstateListing",
        "specVersion": "0.1",
        "assertedBy": _compact(dict(asserted_by)),
        "assertedDate": asserted_date,
        "property": property_ or None,
        "deal": deal or None,
        "lease": lease or None,
        # A fresh assertion has no prior; a re-embed records supersedes = prior payload hash (core).
        "meta": {"supersedes": None},
    })
