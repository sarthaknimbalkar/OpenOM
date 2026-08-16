import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { canonicalize } from "../src/canonicalize.js";

/**
 * CROSS-IMPLEMENTATION REJECTION CONFORMANCE (§C.1). The shared manifest at
 * spec/vectors/rejections/ lists malformed inputs that BOTH implementations MUST reject with the
 * SAME OM-IO-* code. The Python core runs the identical manifest (core/tests/test_rejections.py).
 * Happy-path vectors prove byte-identity; these prove the engines agree on what to refuse — a
 * divergence here is a silent standard fork.
 */
const vectorsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "vectors");

interface RejectionCase {
  name: string;
  input: string;
  code: string;
}
const manifest = JSON.parse(
  readFileSync(join(vectorsDir, "rejections", "manifest.json"), "utf8"),
) as { cases: RejectionCase[] };

describe("cross-impl rejection conformance (shared manifest with the Python core)", () => {
  for (const c of manifest.cases) {
    test(`${c.name} -> ${c.code}`, () => {
      const value = JSON.parse(readFileSync(join(vectorsDir, c.input), "utf8"));
      expect(() => canonicalize(value)).toThrowError(expect.objectContaining({ code: c.code }));
    });
  }
});
