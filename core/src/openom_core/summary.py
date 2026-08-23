# SPDX-License-Identifier: MIT
"""Consumer-side read helper ([Mi22], parity with /js summary.ts).

The typed, formatted flat view a consumer (CRM, underwriting tool, portal) needs so it does not
re-walk the nested payload by hand or mis-render a raw ``0.0625`` cap rate. Pure + deterministic (no
clock, no inference). Field names are camelCase to match the JS ``DealSummary`` so the two views are
directly comparable. Both cores format deterministically (no locale-dependent Intl): USD as ``$``
+ grouped, every other currency as ``"<CUR> <grouped>"`` - BYTE-IDENTICAL to js/src/summary.ts, so
summarize_deal(payload) == summarizeDeal(payload) (guarded by the cross-impl parity test).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, TypedDict


class DealSummary(TypedDict):
    propertyType: str | None
    address: str | None
    buildingSF: float | None
    units: float | None
    askingPrice: float | None
    askingPriceText: str | None
    capRate: float | None
    capRateText: str | None
    noi: float | None
    noiText: str | None
    noiType: str | None
    noiAsOfDate: str | None
    pricePerSF: float | None
    pricePerSFText: str | None
    pricePerUnit: float | None
    pricePerUnitText: str | None
    tenant: str | None
    leaseType: str | None
    commencement: str | None
    expiration: str | None
    termMonths: float | None
    assertedByBroker: str | None
    assertedByBrokerage: str | None
    assertedByLicense: str | None
    assertedDate: str | None
    currency: str


def _obj(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _num(v: Any) -> float | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _str(v: Any) -> str | None:
    return v if isinstance(v, str) and v != "" else None


def summarize_deal(payload: Mapping[str, Any]) -> DealSummary:
    """Turn a payload into a typed, formatted flat view. Pure; deterministic; currency-aware."""
    prop = _obj(payload.get("property"))
    addr = _obj(prop.get("address"))
    deal = _obj(payload.get("deal"))
    lease = _obj(payload.get("lease"))
    by = _obj(payload.get("assertedBy"))
    currency = _str(payload.get("currency")) or "USD"

    def money(v: float | None) -> str | None:
        if v is None:
            return None
        n = math.floor(v + 0.5)  # half-up; matches JS Math.round for cross-impl parity [Mi22]
        return f"${n:,}" if currency == "USD" else f"{currency} {n:,}"

    def money2(v: float | None) -> str | None:
        if v is None:
            return None
        return f"${v:,.2f}" if currency == "USD" else f"{currency} {v:,.2f}"

    def pct(v: float | None) -> str | None:
        return None if v is None else f"{v * 100:.2f}%"

    address_line = (
        ", ".join(
            s
            for s in [
                _str(addr.get("streetAddress")),
                ", ".join(
                    p
                    for p in [_str(addr.get("addressLocality")), _str(addr.get("addressRegion"))]
                    if p
                ),
                _str(addr.get("postalCode")),
            ]
            if s
        )
        or None
    )

    asking = _num(deal.get("askingPrice"))
    cap = _num(deal.get("capRate"))
    noi = _num(deal.get("noi"))
    pps = _num(deal.get("pricePerSF"))
    ppu = _num(deal.get("pricePerUnit"))

    return DealSummary(
        propertyType=_str(prop.get("propertyType")),
        address=address_line,
        buildingSF=_num(prop.get("buildingSF")),
        units=_num(prop.get("units")),
        askingPrice=asking,
        askingPriceText=money(asking),
        capRate=cap,
        capRateText=pct(cap),
        noi=noi,
        noiText=money(noi),
        noiType=_str(deal.get("noiType")),
        noiAsOfDate=_str(deal.get("noiAsOfDate")),
        pricePerSF=pps,
        pricePerSFText=money2(pps),
        pricePerUnit=ppu,
        pricePerUnitText=money(ppu),
        tenant=_str(lease.get("tenantEntity")),
        leaseType=_str(lease.get("leaseTypeAsserted")),
        commencement=_str(lease.get("commencement")),
        expiration=_str(lease.get("expiration")),
        termMonths=_num(lease.get("termMonths")),
        assertedByBroker=_str(by.get("broker")),
        assertedByBrokerage=_str(by.get("brokerage")),
        assertedByLicense=_str(by.get("license")),
        assertedDate=_str(payload.get("assertedDate")),
        currency=currency,
    )
