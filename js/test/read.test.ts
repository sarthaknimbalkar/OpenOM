import { describe, expect, test } from "vitest";
import { readPayloadFromBytes } from "../src/read.js";
import { payloadHash } from "../src/hash.js";
import { buildEmbeddedPdf, buildPlainPdf } from "./fixtures/build-embedded-pdf.js";
import { SAMPLE_STNL } from "./fixtures/sample-stnl.js";

const sample = SAMPLE_STNL as unknown as Record<string, unknown>;

/**
 * §D.2.2 [OM-XMP-005] read orchestration: detect → extract → decompress →
 * verify. States: absent | present | hash-mismatch. Verified against
 * test-synthesized PDFs (embed module + real vectors land after the contract).
 */
describe("readPayloadFromBytes", () => {
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
