import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { OM_SCHEMA, SPEC_VERSION, loadSchema } from "../src/index.js";
import { validatePayload } from "../src/validate.js";

const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const specSchema = JSON.parse(readFileSync(join(specDir, "om-0.1.schema.json"), "utf8"));
const sample = (name: string): Record<string, unknown> =>
  JSON.parse(readFileSync(join(specDir, "samples", `${name}.json`), "utf8")) as Record<
    string,
    unknown
  >;

/**
 * [Bl1] The npm package MUST ship the payload schema so the documented `validatePayload(payload)`
 * path runs from a fresh `npm i openom-js` with no repo clone and no caller-vendored schema - and
 * the bundled copy MUST be byte-equal in VALUE to spec/om-0.1.schema.json (drift-locked), the same
 * guarantee core/schema.py gives the Python side.
 */
describe("[Bl1] bundled OM_SCHEMA", () => {
  test("OM_SCHEMA is exported and deep-equals the committed spec schema (no drift)", () => {
    expect(OM_SCHEMA).toEqual(specSchema);
  });

  test("OM_SCHEMA is the canonical openom.app 0.1 schema", () => {
    expect((OM_SCHEMA as { $id: string }).$id).toContain("openom.app");
  });

  test("SPEC_VERSION reflects the bundled schema's version", () => {
    expect(SPEC_VERSION).toBe("0.1");
  });

  test("loadSchema() returns the same cached bundled object", () => {
    expect(loadSchema()).toBe(OM_SCHEMA);
  });
});

describe("[Bl1/Ma21] validatePayload defaults to the bundled schema (no schema arg)", () => {
  test("a valid payload validates with NO schema argument → not blocked", () => {
    const r = validatePayload(sample("valid-stnl"));
    expect(r.blocked).toBe(false);
    expect(r.errors).toHaveLength(0);
  });

  test("an invalid payload is caught with NO schema argument (default schema is really wired)", () => {
    const r = validatePayload(sample("invalid-caprate-percentage"));
    expect(r.blocked).toBe(true);
    expect(r.errors.length).toBeGreaterThan(0);
  });

  test("an explicit schema argument still works (back-compat)", () => {
    const r = validatePayload(sample("valid-stnl"), specSchema);
    expect(r.blocked).toBe(false);
  });
});
