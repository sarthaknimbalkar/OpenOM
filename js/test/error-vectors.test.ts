import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { describe, expect, test } from "vitest";
import { validatePayload } from "../src/validate.js";

// The TS half of the error differential (the schema-error-tier anti-fork). The Python core
// (gen_error_corpus.py) validated each INVALID payload and committed its sorted {code, path} error
// set; here the TS core (ajv) validates the same payloads and MUST reproduce every set. The two cores
// delegate to different schema engines (jsonschema vs ajv), so this proves the shared normal form
// (required errors at the missing child; ancestor OMV-E001 suppressed) makes their finding lists
// agree - not just the block/allow verdict.
const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "vectors", "errors");
const schema = JSON.parse(
  readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "om-0.1.schema.json"),
    "utf8",
  ),
);
const lines = (name: string): string[] =>
  readFileSync(join(dir, name), "utf8").split("\n").filter(Boolean);

// Compile once (matching validate.ts's own config) so all vectors reuse one validator.
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv, { mode: "full" });
const precompiled = ajv.compile(schema);

describe("error differential - TS core (ajv) matches the Python core (jsonschema)", () => {
  test("every invalid vector produces the expected {code, path} error set", () => {
    const corpus = lines("corpus.jsonl");
    const expected = lines("expected.jsonl");
    expect(corpus.length).toBe(expected.length);
    const mismatches: string[] = [];
    for (let i = 0; i < corpus.length; i++) {
      const c = JSON.parse(corpus[i]!) as { name: string; payload: unknown };
      const r = validatePayload(c.payload, schema, { validate: precompiled });
      expect(r.errors.length, `${c.name} produced no errors`).toBeGreaterThan(0);
      const got = r.errors
        .map((f) => [f.code, f.path])
        .sort((a, b) =>
          a[0]! < b[0]! ? -1 : a[0]! > b[0]! ? 1 : a[1]! < b[1]! ? -1 : a[1]! > b[1]! ? 1 : 0,
        );
      const want = JSON.parse(expected[i]!) as string[][];
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        mismatches.push(`${c.name}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`);
      }
    }
    expect(mismatches).toEqual([]);
  });
});
