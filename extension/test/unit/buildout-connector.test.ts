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

// Reference Buildout connector - maps a listing to a partial openOM payload deterministically, with
// percent→fraction conversion and omit-if-absent. Transport is injected (BuildoutClient).

const LISTING: BuildoutListing = {
  addressLine1: "200 Example Ave",
  city: "Sampletown",
  state: "TX",
  zip: "75000",
  propertyType: "multifamily",
  numberOfUnits: 40,
  occupancyPct: 95,
  askingPrice: 8000000,
  capRatePct: 6,
  noi: 480000,
  pricePerUnit: 200000,
};

describe("buildoutListingToPayload", () => {
  test("maps to a partial openOM payload with percent→fraction conversion", () => {
    const p = buildoutListingToPayload(LISTING) as Record<string, any>;
    expect(p.property.address).toEqual({
      streetAddress: "200 Example Ave",
      addressLocality: "Sampletown",
      addressRegion: "TX",
      postalCode: "75000",
    });
    expect(p.property.units).toBe(40);
    expect(p.property.occupancy).toBe(0.95); // 95% → 0.95
    expect(p.deal.capRate).toBe(0.06); // 6% → 0.06
    expect(p.deal.askingPrice).toBe(8000000);
    expect(p.deal.pricePerUnit).toBe(200000);
  });

  test("omits absent fields - never guesses", () => {
    const p = buildoutListingToPayload({ askingPrice: 5000000 }) as Record<
      string,
      any
    >;
    expect(p.deal).toEqual({ askingPrice: 5000000 });
    expect(p.property).toBeUndefined(); // nothing property-side present
  });

  test("never imports the human-only assertion identity", () => {
    const p = buildoutListingToPayload(LISTING) as Record<string, unknown>;
    expect(p.assertedBy).toBeUndefined();
    expect(p.assertedDate).toBeUndefined();
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
    const partial = await c.fetch("listing-123");
    expect((partial as any).deal.capRate).toBe(0.06);
  });

  test("as a DraftSource it produces JSON-pointer draft fields (deterministic path)", async () => {
    const src = connectorSource(makeBuildoutConnector(client), "listing-123");
    expect(src.deterministic).toBe(true);
    const draft = await src.draft({ pages: [] });
    const byPath = new Map(draft.fields.map((f) => [f.path, f.value]));
    expect(byPath.get("/property/units")).toBe(40);
    expect(byPath.get("/deal/capRate")).toBe(0.06);
    // sanity: the same result the pure mapper would give
    expect(draft).toEqual(
      partialPayloadToFields(
        await client.getListing("x").then(buildoutListingToPayload),
      ),
    );
  });

  test("unconfigured client → not available (picker falls back to on-device)", async () => {
    const off = makeBuildoutConnector({
      isConfigured: async () => false,
      getListing: client.getListing,
    });
    expect(await off.available()).toBe(false);
  });
});
