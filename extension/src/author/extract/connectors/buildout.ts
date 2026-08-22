// Buildout connector (decision memo §3.1), reconciled to the REAL Buildout `get_listing` shape -
// nested `financials` + `core["research_property_attributes.*"]` + `custom_fields.*` (mirrors the
// reference Python mapper cli/src/openom_cli/buildout.py, proven on a live OM). Deterministic, no
// inference: it normalizes names/units and omits anything absent - never guesses.
//
// It emits a PARTIAL openOM payload (property/deal/lease only). The assertion identity
// (assertedBy/assertedDate) and deal.noiType/noiAsOfDate are NOT set here - the review panel is the
// human gate that stamps them ([OM-EXTP-003], memo Q4). The wire call is injected as `BuildoutClient`,
// so transport (HTTP/OAuth MCP, stdio, proxy) is irrelevant here.
import type { StructuredConnector } from "../source.js";

/** The real Buildout get_listing object: nested financials + dotted-key core + custom_fields. */
export interface BuildoutListing {
  financials?: {
    sale_price?: unknown;
    cap_rate?: unknown; // Buildout's stated "Average CAP Rate" (avg over term; often absent)
    cap_rate_derived?: unknown; // current NOI/price - the one we map (matches the consistency check)
    noi?: unknown;
  };
  core?: Record<string, unknown>; // keys like "research_property_attributes.address"
  custom_fields?: Record<string, unknown>;
}

/** The wire seam: whatever fetches a listing (HTTP/OAuth MCP, stdio client, proxy). Injected. */
export interface BuildoutClient {
  isConfigured(): Promise<boolean>;
  getListing(ref: string): Promise<BuildoutListing>;
}

const num = (v: unknown): number | undefined => {
  if (v === null || v === undefined) return undefined;
  const n = Number(String(v).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : undefined;
};
const int = (v: unknown): number | undefined => {
  const n = num(v);
  return n === undefined ? undefined : Math.trunc(n);
};
const pctToFraction = (v: unknown): number | undefined => {
  const n = num(v);
  return n === undefined ? undefined : Math.round((n / 100) * 1e6) / 1e6;
};
/** '10/1/2026' -> '2026-10-01'; undefined if not an M/D/Y date. */
const isoDate = (v: unknown): string | undefined => {
  if (!v) return undefined;
  const p = String(v).trim().split("/");
  if (p.length !== 3) return undefined;
  const [m, d, y] = p.map((x) => Number(x));
  if (![m, d, y].every(Number.isInteger) || m < 1 || m > 12 || d < 1 || d > 31 || y < 1900) {
    return undefined;
  }
  return `${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
};
/** 'GA - Georgia' -> 'GA'; 'GA' -> 'GA'; undefined otherwise. */
const stateCode = (v: unknown): string | undefined => {
  if (!v) return undefined;
  const head = String(v).split("-")[0].trim();
  return head.length === 2 ? head.toUpperCase() : undefined;
};
const leaseType = (v: unknown): string | undefined => {
  if (!v) return undefined;
  const s = String(v).toUpperCase();
  if (s.includes("NNN")) return "NNN";
  if (s.includes("NN")) return "NN";
  if (s.includes("GROSS")) return "gross";
  return String(v);
};

/** Drop absent values (undefined / '' / empty object) so we emit only what Buildout has. */
function compact<T extends Record<string, unknown>>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([, v]) => v !== undefined && v !== "" && !(v && typeof v === "object" && Object.keys(v).length === 0),
    ),
  ) as Partial<T>;
}

/** Map a real Buildout listing -> a PARTIAL openOM payload (property/deal/lease). */
export function buildoutListingToPayload(l: BuildoutListing): Record<string, unknown> {
  const core = l.core ?? {};
  const cf = l.custom_fields ?? {};
  const fin = l.financials ?? {};
  const rp = (attr: string): unknown => core[`research_property_attributes.${attr}`];

  const address = compact({
    streetAddress: rp("address"),
    addressLocality: rp("city"),
    addressRegion: stateCode(rp("state")),
    postalCode: rp("zip"),
    addressCountry: String(rp("country_id")) === "1" ? "US" : undefined,
  });
  const lat = num(rp("latitude"));
  const lng = num(rp("longitude"));
  const geo = lat !== undefined && lng !== undefined ? { latitude: lat, longitude: lng } : undefined;
  const lotAcres = String(rp("lot_size_units") ?? "").toLowerCase().startsWith("acre")
    ? num(rp("lot_size"))
    : undefined;
  const property = compact({
    address: Object.keys(address).length ? address : undefined,
    geo,
    buildingSF: int(rp("building_size")),
    yearBuilt: int(rp("year_built")),
    lotAcres,
    units: int(rp("number_of_units")),
    occupancy: pctToFraction(rp("occupancy_pct")),
  });

  // deal.noiType / noiAsOfDate are the human's at the review gate - NOT imported here (memo Q4).
  const deal = compact({
    askingPrice: int(fin.sale_price),
    capRate: pctToFraction(fin.cap_rate_derived ?? fin.cap_rate),
    noi: int(fin.noi ?? cf.NOI),
    status: "active",
  });

  const guarantorName = cf["Lease guarantor"];
  const lease = compact({
    tenantEntity: cf.Tenant,
    leaseTypeAsserted: leaseType(cf["Lease type"]),
    commencement: isoDate(cf["Lease start date"]),
    expiration: isoDate(cf["Lease expiration date"]),
    guarantor: guarantorName ? { name: guarantorName, type: "corporate" } : undefined,
  });

  return compact({
    property: Object.keys(property).length ? property : undefined,
    deal: Object.keys(deal).length ? deal : undefined,
    lease: Object.keys(lease).length ? lease : undefined,
  });
}

/** Build a `StructuredConnector` over an injected Buildout client. */
export function makeBuildoutConnector(client: BuildoutClient): StructuredConnector {
  return {
    id: "buildout",
    label: "Buildout",
    available: () => client.isConfigured(),
    fetch: async (ref: string) => buildoutListingToPayload(await client.getListing(ref)),
  };
}
