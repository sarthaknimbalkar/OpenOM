import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { canonicalize } from "../src/canonicalize.js";
import { sha256Hex } from "../src/crypto.js";

// #129: the TS half of the cross-language JCS differential fuzz. The 600 edge-weighted vectors were
// canonicalized by the PYTHON core (gen_fuzz_corpus.py) into `expected`; here the TS core canonicalizes
// the SAME corpus and must reproduce every hash byte-for-byte. A single divergence (an ES6 number
// switch-point, a UTF-16 surrogate ordering, an NFC edge) fails here - catching a silent fork of the
// standard that the hand-picked vectors never reach.
const fuzzDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "spec",
  "vectors",
  "fuzz",
);
const lines = (name: string): string[] =>
  readFileSync(join(fuzzDir, name), "utf8").split("\n").filter(Boolean);

describe("JCS differential fuzz - TS core matches the Python core (#129)", () => {
  test("every corpus vector canonicalizes to the expected hash", () => {
    const corpus = lines("corpus.jsonl");
    const expected = lines("expected.jsonl");
    expect(corpus.length).toBe(expected.length);
    expect(corpus.length).toBeGreaterThanOrEqual(500);
    const mismatches: string[] = [];
    for (let i = 0; i < corpus.length; i++) {
      const got = "sha256:" + sha256Hex(canonicalize(JSON.parse(corpus[i]!)));
      if (got !== expected[i])
        mismatches.push(`vector ${i}: ${got} != ${expected[i]}\n  ${corpus[i]}`);
    }
    expect(mismatches).toEqual([]);
  });
});
