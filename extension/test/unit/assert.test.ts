import { describe, expect, test } from "vitest";
import type { ValidationReport } from "openom-js";
import { newDraft, setField } from "../../src/author/draft.js";
import { assertAndEmbed, finalize } from "../../src/author/assert.js";

const profile = { broker: "Jane Broker", brokerage: "Acme CRE", license: "CA-01234567" };
const clean: ValidationReport = {
  specVersion: "0.1",
  validatorVersion: "0.1.0",
  errors: [],
  warnings: [],
  info: [],
  summary: { errorCount: 0, warningCount: 0, infoCount: 0 },
  blocked: false,
};

describe("finalize — the assertion transform", () => {
  test("stamps constants + assertedBy + today; promotes rent source; sets supersedes on reprice", () => {
    let d = newDraft({ lease: { rentSchedule: [{ annualRent: 100, source: "extracted" }] } });
    d = setField(d, "/deal/noi", 100);
    const p = finalize(d, profile, "2026-08-17", { payloadHash: "sha256:prior" });
    expect(p["@type"]).toBe("RealEstateListing");
    expect(p["specVersion"]).toBe("0.1");
    expect((p.assertedBy as Record<string, unknown>).broker).toBe("Jane Broker");
    expect(p["assertedDate"]).toBe("2026-08-17");
    expect(((p.lease as Record<string, unknown[]>).rentSchedule[0] as Record<string, unknown>).source).toBe("asserted");
    expect((p.meta as Record<string, unknown>).supersedes).toBe("sha256:prior");
  });

  test("fresh assertion (no prior) → meta.supersedes is null", () => {
    const p = finalize(newDraft(), profile, "2026-08-17", null);
    expect((p.meta as Record<string, unknown>).supersedes).toBeNull();
  });
});

describe("assertAndEmbed — validate then embed", () => {
  test("schema error → rejects, never embeds", async () => {
    const withError: ValidationReport = { ...clean, errors: [{ code: "OMV-E001", severity: "error", path: "/x", message: "bad" }] };
    let embedded = false;
    await expect(
      assertAndEmbed({}, new Uint8Array(), () => withError, async () => { embedded = true; return new Uint8Array(); }),
    ).rejects.toThrow();
    expect(embedded).toBe(false);
  });

  test("clean → embeds and returns the output bytes", async () => {
    const out = new Uint8Array([9, 9]);
    const r = await assertAndEmbed({}, new Uint8Array([1]), () => clean, async () => out);
    expect(r).toBe(out);
  });
});
