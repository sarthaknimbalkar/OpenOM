import { describe, expect, test } from "vitest";
import {
  connectorSource,
  extractorSource,
  partialPayloadToFields,
  pickDraftSource,
  type DraftSource,
  type StructuredConnector,
} from "../../src/author/extract/source.js";
import type {
  Extractor,
  ExtractionResult,
  PageText,
} from "../../src/author/extract/types.js";

// #166 groundwork: the draft-source seam that lets a deterministic structured connector (Buildout,
// etc.) sit above the inference Extractor seam and take priority over it.

describe("partialPayloadToFields — deterministic partial-payload → draft fields", () => {
  test("maps machine fields to JSON pointers; skips structural + human-only members", () => {
    const partial = {
      "@context": ["x"],
      "@type": "RealEstateListing",
      specVersion: "0.1",
      assertedBy: { broker: "should be skipped" }, // human-only
      meta: { supersedes: null }, // structural
      property: { propertyType: "multifamily", units: 40, occupancy: 0.95 },
      deal: { askingPrice: 8000000, capRate: 0.06, pricePerUnit: 200000 },
    };
    const byPath = new Map(
      partialPayloadToFields(partial).fields.map((f) => [f.path, f.value]),
    );
    expect(byPath.get("/property/units")).toBe(40);
    expect(byPath.get("/property/occupancy")).toBe(0.95);
    expect(byPath.get("/property/propertyType")).toBe("multifamily");
    expect(byPath.get("/deal/askingPrice")).toBe(8000000);
    expect(byPath.get("/deal/pricePerUnit")).toBe(200000);
    // structural + human-only never appear
    expect([...byPath.keys()].some((p) => p.startsWith("/assertedBy"))).toBe(
      false,
    );
    expect([...byPath.keys()].some((p) => p.startsWith("/meta"))).toBe(false);
    expect([...byPath.keys()].some((p) => p.startsWith("/@"))).toBe(false);
    expect(byPath.has("/specVersion")).toBe(false);
  });

  test("indexes arrays (rent schedule) with RFC 6901 pointers", () => {
    const partial = {
      lease: { rentSchedule: [{ annualRent: 100 }, { annualRent: 110 }] },
    };
    const byPath = new Map(
      partialPayloadToFields(partial).fields.map((f) => [f.path, f.value]),
    );
    expect(byPath.get("/lease/rentSchedule/0/annualRent")).toBe(100);
    expect(byPath.get("/lease/rentSchedule/1/annualRent")).toBe(110);
  });

  test("connector fields carry no PDF evidence (structured, not located in the PDF)", () => {
    const fields = partialPayloadToFields({ deal: { noi: 480000 } }).fields;
    expect(fields).toHaveLength(1);
    expect(fields[0]!.evidence).toBeUndefined();
  });
});

describe("pickDraftSource — deterministic connector wins over an inference extractor", () => {
  const fakeExtractor: Extractor = {
    kind: "on-device",
    available: async () => true,
    extract: async (_pages: PageText[]): Promise<ExtractionResult> => ({
      fields: [{ path: "/deal/noi", value: 1 }],
    }),
  };
  const fakeConnector: StructuredConnector = {
    id: "buildout",
    label: "Buildout",
    available: async () => true,
    fetch: async () => ({ deal: { noi: 2 } }),
  };

  test("prefers an available deterministic connector even when an extractor is available", async () => {
    const chosen = await pickDraftSource([
      extractorSource(fakeExtractor, "On-device"),
      connectorSource(fakeConnector, "listing-123"),
    ]);
    expect(chosen?.id).toBe("buildout");
    expect(chosen?.deterministic).toBe(true);
    const draft = await chosen!.draft({ pages: [] });
    expect(draft.fields[0]!.value).toBe(2); // came from the connector, not the extractor
  });

  test("falls back to the inference extractor when no connector is available", async () => {
    const offlineConnector: StructuredConnector = {
      ...fakeConnector,
      available: async () => false,
    };
    const chosen = await pickDraftSource([
      connectorSource(offlineConnector, "x"),
      extractorSource(fakeExtractor, "On-device"),
    ]);
    expect(chosen?.id).toBe("on-device");
    expect(chosen?.deterministic).toBe(false);
  });

  test("returns null when nothing is available (panel falls back to manual entry)", async () => {
    const off: DraftSource = {
      id: "x",
      label: "x",
      deterministic: false,
      available: async () => false,
      draft: async () => ({ fields: [] }),
    };
    expect(await pickDraftSource([off])).toBeNull();
  });
});
