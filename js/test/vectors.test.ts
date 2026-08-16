import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { canonicalize } from "../src/canonicalize.js";
import { sha256Hex } from "../src/crypto.js";

/**
 * CROSS-IMPLEMENTATION PIN. Reproduces the frozen conformance vectors committed
 * by Track A at spec/vectors/ (feat/core @ 9aada7e). The vectors are the oracle
 * — neither implementation certifies itself (§B [OM-VEC-003], §T [OM-REF-001]).
 * `jcs_b64` is the exact canonical byte target; `jcs_sha256` is its digest.
 * A one-byte divergence here is a silent standard fork; it MUST fail loudly.
 */
const vectorsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "vectors");

interface Expected {
  jcs_b64: string;
  jcs_sha256: string;
}
interface ManifestEntry {
  name: string;
  payload: string;
  expected: string;
}

const manifest = JSON.parse(readFileSync(join(vectorsDir, "manifest.json"), "utf8")) as {
  vectors: ManifestEntry[];
};

describe("cross-impl vector pin (spec/vectors @ contract freeze)", () => {
  test("manifest lists the expected seed vectors", () => {
    expect(manifest.vectors.map((v) => v.name).sort()).toEqual([
      "cafe",
      "edge-numbers",
      "edge-unicode",
      "numbers",
      "sample-stnl",
      "unicode",
    ]);
  });

  for (const entry of manifest.vectors) {
    describe(`vector: ${entry.name}`, () => {
      const payload = JSON.parse(readFileSync(join(vectorsDir, entry.payload), "utf8")) as Record<
        string,
        unknown
      >;
      const expected = JSON.parse(
        readFileSync(join(vectorsDir, entry.expected), "utf8"),
      ) as Expected;
      const jcs = canonicalize(payload);

      test("JCS bytes match jcs_b64 exactly (byte-for-byte)", () => {
        expect(Buffer.from(jcs).toString("base64")).toBe(expected.jcs_b64);
      });

      test("SHA-256 matches jcs_sha256", () => {
        expect(`sha256:${sha256Hex(jcs)}`).toBe(expected.jcs_sha256);
      });
    });
  }
});
