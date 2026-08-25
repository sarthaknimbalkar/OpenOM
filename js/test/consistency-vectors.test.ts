import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { validatePayload } from "../src/validate.js";

// The TS half of the consistency differential (the warning/info-tier anti-fork). The Python core
// (gen_consistency_corpus.py) validated each corpus vector and committed its sorted {code, path}
// finding set to expected.jsonl; here the TS core validates the SAME corpus and MUST reproduce every
// set. A rule that fires in one implementation but not the other - the fork the ~30 hand-checked
// consistency rules could silently develop - fails right here. Prose messages and raw expected/actual
// floats are NOT part of the contract; the machine-actionable {code, path} pair is.
const dir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "spec",
  "vectors",
  "consistency",
);
const schema = JSON.parse(
  readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "om-0.1.schema.json"),
    "utf8",
  ),
);
const lines = (name: string): string[] =>
  readFileSync(join(dir, name), "utf8").split("\n").filter(Boolean);

// Compile the schema ONCE (matching validate.ts's own compile config) and reuse it for every vector,
// so the 300+ validations don't each recompile ajv - which otherwise pushes the run past the timeout.
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv, { mode: "full" });
const precompiled = ajv.compile(schema);

describe("consistency differential - TS core matches the Python core", () => {
  test("every corpus vector produces the expected warning+info finding set", () => {
    const corpus = lines("corpus.jsonl");
    const expected = lines("expected.jsonl");
    expect(corpus.length).toBe(expected.length);
    expect(corpus.length).toBeGreaterThanOrEqual(300);
    const mismatches: string[] = [];
    for (let i = 0; i < corpus.length; i++) {
      const payload = JSON.parse(corpus[i]!);
      const r = validatePayload(payload, schema, { validate: precompiled });
      expect(r.errors, `vector ${i} is not schema-valid`).toEqual([]);
      const got = [...r.warnings, ...r.info]
        .map((f) => [f.code, f.path])
        .sort((a, b) =>
          a[0]! < b[0]! ? -1 : a[0]! > b[0]! ? 1 : a[1]! < b[1]! ? -1 : a[1]! > b[1]! ? 1 : 0,
        );
      const want = JSON.parse(expected[i]!) as string[][];
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        mismatches.push(
          `vector ${i}: ${JSON.stringify(got)} != ${JSON.stringify(want)}\n  ${corpus[i]}`,
        );
      }
    }
    expect(mismatches).toEqual([]);
  });
});
