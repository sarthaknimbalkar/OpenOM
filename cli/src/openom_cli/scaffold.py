# SPDX-License-Identifier: MIT
"""Starter payloads for ``om init`` so a CLI user never hits the "no deal.json" dead-end.

Each template mirrors a real, schema-valid committed sample (spec/samples/valid-*.json) so
``om init`` -> ``om validate`` is clean out of the box; the user then swaps the EXAMPLE values for
their deal's. Skeletons are inlined (not read from /spec) because the installed wheel may not ship
the spec directory. The values are examples, called out as such in the guidance ``om init`` prints.
"""

from __future__ import annotations

import copy
from typing import Any

TEMPLATES = ("stnl", "multifamily", "proforma")

# stnl = single-tenant net lease (the most common net-lease OM); the default.
_STNL: dict[str, Any] = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "specVersion": "0.1",
    "assertedBy": {
        "broker": "Your Name", "brokerage": "Your Brokerage", "license": "Your license id",
    },
    "assertedDate": "REPLACED_WITH_TODAY",
    "property": {
        "address": {
            "streetAddress": "1000 Example Rd", "addressLocality": "Sampleville",
            "addressRegion": "MI", "postalCode": "48000", "addressCountry": "US",
        },
        "apn": "00-000-000-000", "buildingSF": 9100, "yearBuilt": 2019,
    },
    "deal": {
        "askingPrice": 1850000, "capRate": 0.0625, "noi": 115625,
        "noiType": "in-place", "noiAsOfDate": "REPLACED_WITH_TODAY", "status": "active",
    },
    "lease": {
        "tenantEntity": "Example Retail Stores, LLC",
        "guarantor": {"name": "Example Retail Corp.", "type": "corporate"},
        "leaseTypeAsserted": "NNN",
        "commencement": "2019-05-01", "expiration": "2034-04-30",
        "rentSchedule": [
            {"periodStart": "2024-05-01", "periodEnd": "2029-04-30", "annualRent": 115625,
             "rentPSF": 12.70, "source": "asserted"},
        ],
    },
    "meta": {"supersedes": None},
}

_MULTIFAMILY: dict[str, Any] = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "specVersion": "0.1",
    "assertedBy": {
        "broker": "Your Name", "brokerage": "Your Brokerage", "license": "Your license id",
    },
    "assertedDate": "REPLACED_WITH_TODAY",
    "property": {
        "propertyType": "multifamily",
        "address": {
            "streetAddress": "200 Example Ave", "addressLocality": "Sampletown",
            "addressRegion": "TX", "postalCode": "75000", "addressCountry": "US",
        },
        "yearBuilt": 1998, "units": 40, "occupancy": 0.95,
    },
    "deal": {
        "askingPrice": 8000000, "capRate": 0.06, "noi": 480000, "noiType": "in-place",
        "noiAsOfDate": "REPLACED_WITH_TODAY", "pricePerUnit": 200000, "status": "active",
    },
    "meta": {"supersedes": None},
}

_PROFORMA: dict[str, Any] = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "specVersion": "0.1",
    "assertedBy": {
        "broker": "Your Name", "brokerage": "Your Brokerage", "license": "Your license id",
    },
    "assertedDate": "REPLACED_WITH_TODAY",
    "currency": "USD",
    "deal": {
        "askingPrice": 5000000, "capRate": 0.07, "noi": 350000, "noiType": "pro-forma",
        "noiAsOfDate": "REPLACED_WITH_TODAY", "status": "active",
    },
    "meta": {"supersedes": None},
}

_SKELETONS: dict[str, dict[str, Any]] = {
    "stnl": _STNL, "multifamily": _MULTIFAMILY, "proforma": _PROFORMA,
}


def build_skeleton(
    template: str, *, today: str, profile_asserted_by: dict[str, str] | None = None
) -> dict[str, Any]:
    """A fresh starter payload: today's date stamped in, ``assertedBy`` filled from the profile."""
    if template not in _SKELETONS:
        raise KeyError(template)
    doc = copy.deepcopy(_SKELETONS[template])
    doc["assertedDate"] = today
    if isinstance(doc.get("deal"), dict) and "noiAsOfDate" in doc["deal"]:
        doc["deal"]["noiAsOfDate"] = today
    if profile_asserted_by:
        for key in ("broker", "brokerage", "license"):
            if profile_asserted_by.get(key):
                doc["assertedBy"][key] = profile_asserted_by[key]
    return doc


def guidance_lines(template: str, out: str, *, has_profile: bool) -> list[str]:
    """The plain-English "now edit these" coaching printed to stderr after writing the file."""
    who = (
        "  - assertedBy.broker / brokerage / license  <-  filled from your saved profile"
        if has_profile
        else "  - assertedBy.broker / brokerage / license  <-  who is asserting this "
        "(or run `om profile set` once to auto-fill)"
    )
    return [
        f"Wrote a starter payload -> {out} (template: {template})",
        "",
        "These are EXAMPLE values - replace them with your deal's, then embed. Key fields:",
        "  - property.address, buildingSF, yearBuilt",
        "  - deal.askingPrice (dollars, e.g. 1850000), deal.noi (dollars)",
        "  - deal.capRate  <-  a DECIMAL fraction: 6.25% = 0.0625  (NOT 6.25)",
        "  - deal.noiType  <-  'in-place' or 'pro-forma'  (required whenever you set an NOI)",
        who,
        "",
        "Next:",
        f"  om validate {out}          # plain-English check before you embed",
        f"  om embed listing.pdf --payload {out} --out listing.openom.pdf "
        f"--asserted-date {_stamp_hint()}",
        "",
        "Not a developer? You don't need any of this - embed in your browser (nothing leaves your "
        "machine): https://openom.app/embed/",
    ]


def _stamp_hint() -> str:
    # A literal placeholder in the printed example command (not a real date - keeps output stable).
    return "<today>"
