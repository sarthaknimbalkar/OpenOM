import { describe, expect, test } from "vitest";
import schema from "../../../spec/om-0.1.schema.json";
import { schemaExpectedPaths } from "../../src/author/schema-paths.js";
import { suggestedFilename } from "../../src/author/assert.js";
import { looksLikePdf } from "../../src/author/capture.js";

describe("schemaExpectedPaths (#92)", () => {
  const paths = schemaExpectedPaths(schema as { properties?: Record<string, unknown> });
  test("covers the field map far beyond a hardcoded handful", () => {
    expect(paths.length).toBeGreaterThan(10);
    expect(paths).toContain("/deal/askingPrice");
    expect(paths).toContain("/deal/capRate");
    expect(paths).toContain("/property/address/streetAddress");
    expect(paths).toContain("/lease/tenantEntity");
  });
  test("excludes gate-set noi fields", () => {
    expect(paths).not.toContain("/deal/noiType");
    expect(paths).not.toContain("/deal/noiAsOfDate");
  });
});

describe("suggestedFilename (#99)", () => {
  test("derives a slug from the street address", () => {
    expect(suggestedFilename({ property: { address: { streetAddress: "1000 Example Rd" } } })).toBe(
      "1000-example-rd-openom.pdf",
    );
  });
  test("falls back to the source URL basename, then the default", () => {
    expect(suggestedFilename({}, "https://x.com/listings/deal-123.pdf")).toBe("deal-123-openom.pdf");
    expect(suggestedFilename({})).toBe("openom-embedded.pdf");
  });
});

describe("looksLikePdf (#65)", () => {
  test("true for %PDF- bytes, false for HTML", () => {
    expect(looksLikePdf(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]))).toBe(true);
    expect(looksLikePdf(new TextEncoder().encode("<!doctype html>"))).toBe(false);
  });
});
