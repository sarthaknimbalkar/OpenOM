// Consumer-side read helper ([M3]) - the typed, formatted flat view every consumer (CRM, underwriting
// tool, portal, the extension popup) needs, so none of them re-walk the nested payload by hand or
// mis-render a raw `0.0625` cap rate. Deterministic + pure (no clock, no inference). Formatting uses
// Intl with the payload's own `currency`; raw values are kept alongside the display strings.

export interface DealSummary {
  propertyType: string | null;
  address: string | null; // one-line "123 Main St, City, ST 00000"
  buildingSF: number | null;
  units: number | null;
  askingPrice: number | null;
  askingPriceText: string | null;
  capRate: number | null; // raw fraction, e.g. 0.0625
  capRateText: string | null; // "6.25%"
  noi: number | null;
  noiText: string | null;
  noiType: string | null; // in-place | pro-forma
  noiAsOfDate: string | null;
  pricePerSF: number | null;
  pricePerSFText: string | null;
  pricePerUnit: number | null;
  pricePerUnitText: string | null;
  tenant: string | null;
  leaseType: string | null;
  commencement: string | null;
  expiration: string | null;
  termMonths: number | null;
  assertedByBroker: string | null;
  assertedByBrokerage: string | null;
  assertedByLicense: string | null;
  assertedDate: string | null;
  currency: string;
}

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}
function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function str(v: unknown): string | null {
  return typeof v === "string" && v !== "" ? v : null;
}

/** Turn a payload into a typed, formatted flat view. Pure; deterministic; currency-aware. */
export function summarizeDeal(payload: Record<string, unknown>): DealSummary {
  const property = obj(payload.property);
  const addr = obj(property.address);
  const deal = obj(payload.deal);
  const lease = obj(payload.lease);
  const by = obj(payload.assertedBy);
  const currency = str(payload.currency) ?? "USD";

  // [Mi22] Deterministic, currency-aware formatting that is BYTE-IDENTICAL to the Python
  // summarize_deal (no locale-dependent Intl) so the two views match for a cross-impl parity vector.
  // USD renders with a "$" prefix; every other currency as "<CUR> <grouped>".
  const group = (n: number): string => n.toLocaleString("en-US"); // "1,850,000"
  const group2 = (n: number): string =>
    n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money = (v: number | null): string | null => {
    if (v === null) return null;
    const n = Math.round(v); // half-up; matches Python floor(v + 0.5)
    return currency === "USD" ? `$${group(n)}` : `${currency} ${group(n)}`;
  };
  const money2 = (v: number | null): string | null => {
    if (v === null) return null;
    return currency === "USD" ? `$${group2(v)}` : `${currency} ${group2(v)}`;
  };
  const pct = (v: number | null): string | null => (v === null ? null : `${(v * 100).toFixed(2)}%`);

  const addressLine =
    [
      str(addr.streetAddress),
      [str(addr.addressLocality), str(addr.addressRegion)].filter(Boolean).join(", "),
      str(addr.postalCode),
    ]
      .filter((s) => s && s.length)
      .join(", ") || null;

  const askingPrice = num(deal.askingPrice);
  const capRate = num(deal.capRate);
  const noi = num(deal.noi);
  const pricePerSF = num(deal.pricePerSF);
  const pricePerUnit = num(deal.pricePerUnit);

  return {
    propertyType: str(property.propertyType),
    address: addressLine,
    buildingSF: num(property.buildingSF),
    units: num(property.units),
    askingPrice,
    askingPriceText: money(askingPrice),
    capRate,
    capRateText: pct(capRate),
    noi,
    noiText: money(noi),
    noiType: str(deal.noiType),
    noiAsOfDate: str(deal.noiAsOfDate),
    pricePerSF,
    pricePerSFText: money2(pricePerSF),
    pricePerUnit,
    pricePerUnitText: money(pricePerUnit),
    tenant: str(lease.tenantEntity),
    leaseType: str(lease.leaseTypeAsserted),
    commencement: str(lease.commencement),
    expiration: str(lease.expiration),
    termMonths: num(lease.termMonths),
    assertedByBroker: str(by.broker),
    assertedByBrokerage: str(by.brokerage),
    assertedByLicense: str(by.license),
    assertedDate: str(payload.assertedDate),
    currency,
  };
}
