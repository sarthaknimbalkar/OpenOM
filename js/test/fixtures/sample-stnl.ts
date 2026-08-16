/**
 * A self-authored, fictional STNL sample payload for contract-free round-trip
 * tests. Replaced by `/spec/samples/` once Track A's contract PR lands.
 * Shape follows §7e / §E; values are invented.
 */
export const SAMPLE_STNL = {
  "@context": ["https://schema.org", "https://SPEC-DOMAIN-TBD/ns/0.1"],
  "@type": "RealEstateListing",
  specVersion: "0.1",
  currency: "USD",
  assertedBy: {
    broker: "Jane Example",
    brokerage: "Example Net Lease Advisors",
    license: "MI 6501-000000",
  },
  assertedDate: "2026-08-15",
  deal: {
    askingPrice: 1850000,
    capRate: 0.0625,
    noi: 115625,
    noiType: "in-place",
    noiAsOfDate: "2026-06-30",
    status: "active",
  },
  meta: { supersedes: null },
} as const;
