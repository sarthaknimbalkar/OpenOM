# SPDX-License-Identifier: MIT
"""Deterministic CSV row -> openOM payload mapper (the spreadsheet on-ramp for bulk seeding).

A broker with a back catalog usually has a spreadsheet + a folder of PDFs, not Buildout JSON. This
maps one CSV row (a documented canonical column set) to a schema-valid openOM payload, ready for
``om embed-batch`` - the same output shape as the Buildout bridge, different input. Pure + zero
inference: every value comes from the broker's own cell (that IS the assertion); absent cells are
omitted, never guessed. The assertion identity (assertedBy / assertedDate / noiType / noiAsOfDate)
is supplied by the caller and stamped verbatim.

Numeric/date/state normalization reuses the SAME helpers as the Buildout mapper, so a number, a
percent, or an M/D/Y date maps identically on both on-ramps. Percentage columns are named ``*Pct``
(e.g. ``capRatePct`` = 6.25, not 0.0625) so a non-technical broker can't misread the unit.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .buildout import (
    NS,
    _compact,
    _int,
    _iso_date,
    _lease_type,
    _months_between,
    _num,
    _pct_to_fraction,
    _round_half_up,
    _state_code,
)

# The canonical header vocabulary a broker fills in. Order is the template's column order. Every
# column is optional except that a row must name its PDF (an ``id`` -> <id>.pdf, or an explicit
# ``pdf`` filename) and produce a schema-valid payload. ``*Pct`` columns are percentages.
CANONICAL_COLUMNS: tuple[str, ...] = (
    "id", "pdf",
    "broker", "brokerage", "license", "noiType", "noiAsOfDate",
    "streetAddress", "city", "state", "postalCode", "country",
    "propertyType", "buildingSF", "yearBuilt", "lotAcres", "units", "occupancyPct",
    "latitude", "longitude",
    "askingPrice", "capRatePct", "noi", "status",
    "tenant", "leaseType", "commencement", "expiration", "guarantor",
)

# Per-row overrides of the assertion identity (a catalog can span brokers / NOI types).
_OVERRIDE_COLUMNS: tuple[str, ...] = ("broker", "brokerage", "license", "noiType", "noiAsOfDate")

_EXAMPLE_ROW: dict[str, str] = {
    "id": "123-main", "pdf": "123-main.pdf",
    "streetAddress": "123 Main St", "city": "Austin", "state": "TX", "postalCode": "78701",
    "propertyType": "retail", "buildingSF": "9100", "yearBuilt": "2019",
    "askingPrice": "1850000", "capRatePct": "6.25", "noi": "115625",
    "tenant": "Example Retail, LLC", "leaseType": "NNN",
    "commencement": "5/1/2019", "expiration": "4/30/2034",
}


def _cell(row: Mapping[str, str], key: str) -> str | None:
    """A trimmed cell value, or None when the column is absent/blank (so _compact drops it)."""
    v = row.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _date(v: str | None) -> str | None:
    """Accept either an ISO date (pass-through) or an M/D/Y spreadsheet date."""
    if not v:
        return None
    s = str(v).strip()
    parts = s.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:  # already ISO-ish -> validate via round-trip
        try:
            y, m, d = (int(p) for p in parts)
        except ValueError:
            return None
        if 1 <= m <= 12 and 1 <= d <= 31 and y > 1900:
            return f"{y:04d}-{m:02d}-{d:02d}"
        return None
    return _iso_date(s)


def override_identity(row: Mapping[str, str]) -> dict[str, str]:
    """The per-row assertion-identity overrides present in this row (subset of the override set)."""
    return {k: v for k in _OVERRIDE_COLUMNS if (v := _cell(row, k)) is not None}


def row_to_payload(
    row: Mapping[str, str],
    *,
    asserted_by: dict[str, str],
    asserted_date: str,
    noi_type: str,
    noi_as_of: str | None = None,
) -> dict[str, Any]:
    """Map one canonical CSV row to a schema-valid openOM payload (only the fields the row carries).
    ``asserted_by``/``asserted_date``/``noi_type``/``noi_as_of`` are the assertion identity and are
    stamped verbatim, never inferred from the row."""
    address = _compact({
        "streetAddress": _cell(row, "streetAddress"),
        "addressLocality": _cell(row, "city"),
        "addressRegion": _state_code(_cell(row, "state")),
        "postalCode": _cell(row, "postalCode"),
        "addressCountry": _cell(row, "country") or ("US" if _cell(row, "state") else None),
    })
    lat, lng = _num(_cell(row, "latitude")), _num(_cell(row, "longitude"))
    geo = {"latitude": lat, "longitude": lng} if lat is not None and lng is not None else None
    building_sf = _int(_cell(row, "buildingSF"))
    units = _int(_cell(row, "units"))
    prop_type = _cell(row, "propertyType")
    property_ = _compact({
        "propertyType": prop_type.lower() if prop_type else None,
        "address": address or None,
        "geo": geo,
        "buildingSF": building_sf,
        "yearBuilt": _int(_cell(row, "yearBuilt")),
        "lotAcres": _num(_cell(row, "lotAcres")),
        "units": units,
        "occupancy": _pct_to_fraction(_cell(row, "occupancyPct")),
    })

    price = _int(_cell(row, "askingPrice"))
    deal = _compact({
        "askingPrice": price,
        "capRate": _pct_to_fraction(_cell(row, "capRatePct")),
        "noi": _int(_cell(row, "noi")),
        "pricePerUnit": int(_round_half_up(price / units)) if price and units else None,
        "pricePerSF": _round_half_up(price / building_sf, 2) if price and building_sf else None,
        "noiType": noi_type,
        "noiAsOfDate": noi_as_of or asserted_date,
        "status": _cell(row, "status") or "active",
    })

    commencement = _date(_cell(row, "commencement"))
    expiration = _date(_cell(row, "expiration"))
    guarantor_name = _cell(row, "guarantor")
    lease = _compact({
        "tenantEntity": _cell(row, "tenant"),
        "leaseTypeAsserted": _lease_type(_cell(row, "leaseType")),
        "commencement": commencement,
        "expiration": expiration,
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
        "meta": {"supersedes": None},
    })


def template_csv() -> str:
    """A blank template: the canonical header row + one worked example, so a broker knows exactly
    what to fill in. Assertion identity (broker/brokerage/license/noiType) normally comes from the
    command flags; the columns exist only for a catalog that spans brokers."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")  # csv.writer quotes cells containing commas
    writer.writerow(CANONICAL_COLUMNS)
    writer.writerow([_EXAMPLE_ROW.get(c, "") for c in CANONICAL_COLUMNS])
    return buf.getvalue()
