import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readPayloadFromBytes } from "../src/read.js";
import { pdfjsDecryptRead } from "../src/read-decrypt.js";

/**
 * CROSS-IMPL pathology conformance (#11): the JS consumer (pdf-lib) reads the SAME committed
 * golden PDFs the Python producer embedded (spec/vectors/pathologies/) - an image-only scan, a
 * minimal payload, and an empty-password-encrypted document. Regenerate the goldens with
 * `python -m spec.vectors.build_pathologies`.
 */
const dir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "spec",
  "vectors",
  "pathologies",
);
const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8")) as {
  cases: { name: string; pdf: string; expected: string; encrypted?: boolean }[];
};

describe("pathology golden PDFs - JS consumer reads the Python-produced payload", () => {
  for (const c of manifest.cases) {
    test(`${c.name} round-trips`, async () => {
      const bytes = new Uint8Array(readFileSync(join(dir, c.pdf)));
      const expected = JSON.parse(readFileSync(join(dir, c.expected), "utf8"));
      // The encrypted golden needs the opt-in pdf.js decrypt fallback (#106); others load via pdf-lib.
      const result = await readPayloadFromBytes(bytes, c.encrypted ? pdfjsDecryptRead : undefined);
      expect(result.state).toBe("present");
      expect(result.verification.hashValid).toBe(true);
      expect(result.payload).toEqual(expected);
    });
  }
});
