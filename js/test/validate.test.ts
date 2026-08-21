import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { validatePayload } from "../src/validate.js";

const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const schema = JSON.parse(readFileSync(join(specDir, "om-0.1.schema.json"), "utf8"));
const sample = (name: string) =>
  JSON.parse(readFileSync(join(specDir, "samples", `${name}.json`), "utf8")) as Record<
    string,
    unknown
  >;

/**
 * §H schema-error tier (VAL-01). Errors (OMV-E###) block; the report envelope
 * and `blocked = errorCount > 0` follow [OM-ERR-010]. Verified against the
 * committed spec/samples/.
 */
describe("validatePayload - schema tier", () => {
  test("valid-stnl passes with zero errors and blocked=false", () => {
    const r = validatePayload(sample("valid-stnl"), schema);
    expect(r.errors).toEqual([]);
    expect(r.blocked).toBe(false);
    expect(r.summary.errorCount).toBe(0);
  });

  test("blocked equals errorCount > 0", () => {
    const r = validatePayload(sample("invalid-caprate-percentage"), schema);
    expect(r.blocked).toBe(r.summary.errorCount > 0);
    expect(r.blocked).toBe(true);
  });

  test("capRate as a percentage (6.25 > 1) → OMV-E001 at /deal/capRate", () => {
    const r = validatePayload(sample("invalid-caprate-percentage"), schema);
    const codes = r.errors.map((e) => e.code);
    expect(codes).toContain("OMV-E001");
    expect(r.errors.some((e) => e.code === "OMV-E001" && e.path === "/deal/capRate")).toBe(true);
  });

  test("noi present but noiType/noiAsOfDate missing → OMV-E002", () => {
    const r = validatePayload(sample("invalid-missing-noitype"), schema);
    expect(r.errors.map((e) => e.code)).toContain("OMV-E002");
  });

  test("malformed meta.signature → OMV-E003 at /meta/signature", () => {
    const r = validatePayload(sample("invalid-populated-signature"), schema);
    expect(r.errors.some((e) => e.code === "OMV-E003" && e.path === "/meta/signature")).toBe(true);
  });

  test("reserved signature shape + optional identity/type/ext fields validate cleanly (#117/#118/#114/#115)", () => {
    const p = sample("valid-stnl");
    (p.meta as Record<string, unknown>).signature = {
      alg: "ed25519",
      keyId: "did:key:z6Mk",
      value: "BASE64SIG",
    };
    (p.property as Record<string, unknown>).propertyType = "retail";
    (p.assertedBy as Record<string, unknown>).website = "https://example.com";
    (p.assertedBy as Record<string, unknown>).licenseJurisdiction = "US-CA";
    p.ext = { acme: { internalId: 42 } };
    const r = validatePayload(p, schema);
    expect(r.errors.some((e) => e.code === "OMV-E003")).toBe(false);
    expect(r.blocked).toBe(false);
  });

  test("findings are deterministically ordered (severity, code, path)", () => {
    const r = validatePayload(sample("invalid-caprate-percentage"), schema);
    const keys = r.errors.map((e) => `${e.code} ${e.path}`);
    expect(keys).toEqual([...keys].sort());
  });
});

/**
 * Cross-implementation conformance matrix (spec §B [OM-VEC-004]). Both implementations MUST
 * reproduce these schema-tier outcomes; Track A runs the same spec/samples/manifest.json.
 */
interface SampleEntry {
  name: string;
  valid: boolean;
  errorCodes: string[];
  warningCodes?: string[];
}
const sampleManifest = JSON.parse(
  readFileSync(join(specDir, "samples", "manifest.json"), "utf8"),
) as { samples: SampleEntry[] };

describe("conformance sample matrix (shared with the Python core)", () => {
  for (const entry of sampleManifest.samples) {
    test(`${entry.name}: ${entry.valid ? "valid" : entry.errorCodes.join(",")}`, () => {
      const r = validatePayload(sample(entry.name), schema);
      const codes = r.errors.map((e) => e.code);
      if (entry.valid) {
        expect(r.errors).toEqual([]);
        expect(r.blocked).toBe(false);
      } else {
        expect(r.blocked).toBe(true);
        for (const code of entry.errorCodes) expect(codes).toContain(code);
      }
      // Consistency-tier parity: warning codes both implementations must reproduce.
      const warnCodes = r.warnings.map((w) => w.code);
      for (const code of entry.warningCodes ?? []) expect(warnCodes).toContain(code);
    });
  }
});
