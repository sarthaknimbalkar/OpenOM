// Reference Buildout connector (decision memo §3.1; Q2 decided by design). It maps a Buildout
// listing record onto a PARTIAL openOM payload — deterministic, no inference, no PDF. The concrete
// wire call is INJECTED as `BuildoutClient`, so transport is irrelevant here: an HTTP/OAuth MCP call,
// a stdio MCP client, or a hosted author-service proxy all satisfy the same interface (memo §3.3 Q1).
//
// The `BuildoutListing` shape below is the openOM-optimal fit, not a copy of Buildout's live API. When
// the real Buildout MCP is wired, the only change is reconciling FIELD NAMES + units in `getListing`
// and in the mapping — the structure, the seam, the mapper, and the gate are all already in place.
import type { StructuredConnector } from "../source.js";

/**
 * A Buildout listing record (assumed shape — reconcile names/units with the real MCP response).
 * All fields optional: the broker may not have every one, and we emit only what's present
 * (never guess). Rates/occupancy are assumed to arrive as PERCENTAGES (Buildout's UI convention)
 * and are converted to openOM's decimal-fraction convention here.
 */
export interface BuildoutListing {
  addressLine1?: string;
  city?: string;
  state?: string;
  zip?: string;
  propertyType?: string; // Buildout asset-type label; openOM propertyType is an open string
  buildingSqFt?: number;
  yearBuilt?: number;
  numberOfUnits?: number;
  occupancyPct?: number; // e.g. 95 (percent) → openOM property.occupancy 0.95
  askingPrice?: number;
  capRatePct?: number; // e.g. 6.25 (percent) → openOM deal.capRate 0.0625
  noi?: number;
  pricePerSqFt?: number;
  pricePerUnit?: number;
}

/** The wire seam: whatever fetches a listing (HTTP/OAuth MCP, stdio client, proxy). Injected. */
export interface BuildoutClient {
  isConfigured(): Promise<boolean>;
  getListing(ref: string): Promise<BuildoutListing>;
}

/** Drop `undefined` values so the partial payload carries only fields the broker actually has. */
function compact<T extends Record<string, unknown>>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined),
  ) as Partial<T>;
}

const pct = (v: number | undefined): number | undefined =>
  v === undefined ? undefined : v / 100;

/** Map a Buildout listing → a PARTIAL openOM payload (the connector's only real logic). */
export function buildoutListingToPayload(
  l: BuildoutListing,
): Record<string, unknown> {
  const address = compact({
    streetAddress: l.addressLine1,
    addressLocality: l.city,
    addressRegion: l.state,
    postalCode: l.zip,
  });
  const property = compact({
    propertyType: l.propertyType,
    address: Object.keys(address).length ? address : undefined,
    buildingSF: l.buildingSqFt,
    yearBuilt: l.yearBuilt,
    units: l.numberOfUnits,
    occupancy: pct(l.occupancyPct), // percent → decimal fraction (openOM convention)
  });
  const deal = compact({
    askingPrice: l.askingPrice,
    capRate: pct(l.capRatePct), // percent → decimal fraction
    noi: l.noi,
    pricePerSF: l.pricePerSqFt,
    pricePerUnit: l.pricePerUnit,
  });
  // assertedBy / assertedDate / noiType are NOT imported — the human stamps them at the review gate.
  return compact({
    property: Object.keys(property).length ? property : undefined,
    deal: Object.keys(deal).length ? deal : undefined,
  });
}

/** Build a `StructuredConnector` over an injected Buildout client. */
export function makeBuildoutConnector(
  client: BuildoutClient,
): StructuredConnector {
  return {
    id: "buildout",
    label: "Buildout",
    available: () => client.isConfigured(),
    fetch: async (ref: string) =>
      buildoutListingToPayload(await client.getListing(ref)),
  };
}
