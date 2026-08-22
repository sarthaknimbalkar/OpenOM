import { describe, expect, test } from "vitest";
import {
  buildoutListingToPayload,
  makeBuildoutConnector,
  type BuildoutClient,
  type BuildoutListing,
} from "../../src/author/extract/connectors/buildout.js";
import {
  connectorSource,
  partialPayloadToFields,
} from "../../src/author/extract/source.js";

// Reconciled to the REAL Buildout get_listing shape (nested financials + core + custom_fields).
// Maps to a PARTIAL openOM payload deterministically; percent->fraction (cap_rate_derived),
// M/D/Y->ISO, "MI - Michigan"->"MI", "Absolute NNN"->"NNN"; omit-if-absent. Mirrors the Python mapper.

const LISTING: BuildoutListing = {
  financials: { sale_price: 1850000, cap_rate: 6.5, cap_rate_derived: 6.25, noi: 115625 },
  core: {
    "research_property_attributes.address": "1000 Example Rd",
    "research_property_attributes.city": "Sampleville",
    "research_property_attributes.state": "MI - Michigan",
    "research_property_attributes.zip": "48000",
    "research_property_attributes.country_id": "1",
    "research_property_attributes.building_size": "9100.0",
    "research_property_attributes.year_built": "2019",
    "research_property_attributes.occupancy_pct": "100.0",
    "research_property_attributes.number_of_units": "1",
    "research_property_attributes.lot_size": "1.25",
    "research_property_attributes.lot_size_units": "Acres",
  },
  custom_fields: {
    Tenant: "Example Retail Stores, LLC",
    "Lease type": "Absolute NNN",
    "Lease start date": "5/1/2019",
    "Lease expiration date": "4/30/2034",
    "Lease guarantor": "Example Retail Corp.",
    NOI: "115625",
  },
};

describe("buildoutListingToPayload (real nested shape)", () => {
  test("maps address, units/units, and financials with derived cap %->fraction", () => {
    const p = buildoutListingToPayload(LISTING) as Record<string, any>;
    expect(p.property.address).toEqual({
      streetAddress: "1000 Example Rd",
      addressLocality: "Sampleville",
      addressRegion: "MI",
      postalCode: "48000",
      addressCountry: "US",
    });
    expect(p.property.buildingSF).toBe(9100);
    expect(p.property.lotAcres).toBe(1.25);
    expect(p.property.units).toBe(1);
    expect(p.property.occupancy).toBe(1); // 100% -> 1.0
    expect(p.deal.askingPrice).toBe(1850000);
    expect(p.deal.capRate).toBe(0.0625); // cap_rate_derived 6.25 -> 0.0625 (matches NOI/price)
    expect(p.deal.noi).toBe(115625);
  });

  test("maps lease terms: tenant, NNN, ISO dates, guarantor", () => {
    const p = buildoutListingToPayload(LISTING) as Record<string, any>;
    expect(p.lease.tenantEntity).toBe("Example Retail Stores, LLC");
    expect(p.lease.leaseTypeAsserted).toBe("NNN"); // "Absolute NNN" -> "NNN"
    expect(p.lease.commencement).toBe("2019-05-01"); // 5/1/2019 -> ISO
    expect(p.lease.expiration).toBe("2034-04-30");
    expect(p.lease.guarantor).toEqual({ name: "Example Retail Corp.", type: "corporate" });
  });

  test("never imports the human-gated assertion identity or noiType (memo Q4)", () => {
    const p = buildoutListingToPayload(LISTING) as Record<string, any>;
    expect(p.assertedBy).toBeUndefined();
    expect(p.assertedDate).toBeUndefined();
    expect(p.deal.noiType).toBeUndefined();
    expect(p.deal.noiAsOfDate).toBeUndefined();
  });

  test("omits absent fields - never guesses", () => {
    const p = buildoutListingToPayload({ financials: { sale_price: 5000000 } }) as Record<
      string,
      any
    >;
    expect(p.deal).toEqual({ askingPrice: 5000000, status: "active" });
    expect(p.property).toBeUndefined();
    expect(p.lease).toBeUndefined();
  });
});

describe("makeBuildoutConnector - flows through the draft-source seam", () => {
  const client: BuildoutClient = {
    isConfigured: async () => true,
    getListing: async () => LISTING,
  };

  test("available reflects the client; fetch yields a partial payload", async () => {
    const c = makeBuildoutConnector(client);
    expect(c.id).toBe("buildout");
    expect(await c.available()).toBe(true);
    const partial = await c.fetch("listing-1");
    expect((partial as any).deal.capRate).toBe(0.0625);
  });

  test("as a DraftSource it produces JSON-pointer draft fields (deterministic path)", async () => {
    const src = connectorSource(makeBuildoutConnector(client), "listing-1");
    expect(src.deterministic).toBe(true);
    const draft = await src.draft({ pages: [] });
    const byPath = new Map(draft.fields.map((f) => [f.path, f.value]));
    expect(byPath.get("/deal/capRate")).toBe(0.0625);
    expect(byPath.get("/lease/tenantEntity")).toBe("Example Retail Stores, LLC");
    expect(draft).toEqual(
      partialPayloadToFields(
        await client.getListing("x").then(buildoutListingToPayload),
      ),
    );
  });

  test("unconfigured client -> not available (picker falls back to on-device)", async () => {
    const off = makeBuildoutConnector({
      isConfigured: async () => false,
      getListing: client.getListing,
    });
    expect(await off.available()).toBe(false);
  });
});
