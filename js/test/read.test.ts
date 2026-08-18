import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readPayloadFromBytes } from "../src/read.js";
import { payloadHash } from "../src/hash.js";
import { buildEmbeddedPdf, buildPlainPdf } from "./fixtures/build-embedded-pdf.js";
import { SAMPLE_STNL } from "./fixtures/sample-stnl.js";

const vectorsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "vectors");

const sample = SAMPLE_STNL as unknown as Record<string, unknown>;

/**
 * §D.2.2 [OM-XMP-005] read orchestration: detect → extract → decompress →
 * verify. States: absent | present | hash-mismatch. Verified against
 * test-synthesized PDFs (embed module + real vectors land after the contract).
 */
describe("readPayloadFromBytes", () => {
  // #113: the committed negative-state golden vectors (shared manifest with the Python core).
  test("negative-state goldens read as their expected state", async () => {
    const manifest = JSON.parse(
      readFileSync(join(vectorsDir, "negatives", "manifest.json"), "utf8"),
    ) as { cases: { name: string; pdf: string; expectState: string }[] };
    expect(manifest.cases.length).toBeGreaterThan(0);
    for (const c of manifest.cases) {
      const r = await readPayloadFromBytes(new Uint8Array(readFileSync(join(vectorsDir, c.pdf))));
      expect(r.state, c.name).toBe(c.expectState);
      if (c.expectState === "hash-mismatch") expect(r.verification.hashValid, c.name).toBe(false);
    }
  });

  test("absent: a PDF with no payload → state 'absent', null payload", async () => {
    const r = await readPayloadFromBytes(await buildPlainPdf());
    expect(r.state).toBe("absent");
    expect(r.payload).toBeNull();
    expect(r.verification.hashValid).toBeNull();
  });

  test("present: embedded payload verifies → state 'present', hashValid true, exact payload", async () => {
    const r = await readPayloadFromBytes(await buildEmbeddedPdf(sample));
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
    expect(r.payloadHash).toBe(payloadHash(sample));
    expect(r.payload).toEqual(sample);
  });

  test("present: origin/signature verification are null in 0.1 (not false)", async () => {
    const r = await readPayloadFromBytes(await buildEmbeddedPdf(sample));
    expect(r.verification.originVerified).toBeNull();
    expect(r.verification.signatureValid).toBeNull();
  });

  test("hash-mismatch: XMP hash disagrees → state 'hash-mismatch', hashValid false, payload still returned", async () => {
    const wrongHash = "sha256:" + "0".repeat(64);
    const r = await readPayloadFromBytes(
      await buildEmbeddedPdf(sample, { overridePayloadHash: wrongHash }),
    );
    expect(r.state).toBe("hash-mismatch");
    expect(r.verification.hashValid).toBe(false);
    expect(r.payload).not.toBeNull(); // OM-VAL-006: returned, but not trusted
  });

  test("degraded: payload present but no XMP hash → integrity-unverified, hashValid not true (OM-XMP-008)", async () => {
    const r = await readPayloadFromBytes(await buildEmbeddedPdf(sample, { omitXmpHash: true }));
    expect(r.verification.hashValid).not.toBe(true);
    expect(r.payload).not.toBeNull();
  });
});
