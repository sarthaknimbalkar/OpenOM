import { describe, expect, test } from "vitest";
import { integrityHashOfBytes, verifyIntegrity } from "../src/verify.js";

/**
 * §C.4/§X.4 [OM-VAL-006] + [OM-CANON-008] Consumer verification.
 * The tamper check hashes the received decompressed bytes EXACTLY as-is - no
 * re-parse, no NFC, no re-canonicalization - and compares to omspec:payloadHash.
 * Re-normalizing would mask a genuine mismatch.
 */

// The exact bytes a conformant Producer stores for §C.5 Example 4 (meta.signature
// absent in 0.1) - this IS the preimage JCS, 248 bytes.
const STORED = new TextEncoder().encode(
  '{"assertedDate":"2026-08-15","deal":{"askingPrice":1850000,"capRate":0.0625,"noi":115625,"noiType":"in-place"},"meta":{"sourceDocHash":"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","supersedes":null},"specVersion":"0.1"}',
);
const EXPECTED = "sha256:aa631ed617b85ac226ef4f6ae97e5387a60fdc51c6e49f42c35034c113ca16f7";

describe("integrityHashOfBytes", () => {
  test("hashes raw bytes to the §C.5 Example 4 integrity hash", () => {
    expect(integrityHashOfBytes(STORED)).toBe(EXPECTED);
  });
});

describe("verifyIntegrity", () => {
  test("hashValid=true when bytes match the expected hash", () => {
    const r = verifyIntegrity(STORED, EXPECTED);
    expect(r.hashValid).toBe(true);
    expect(r.computedHash).toBe(EXPECTED);
  });

  test("hashValid=false on a single-byte tamper (never re-normalized)", () => {
    const tampered = STORED.slice();
    tampered[20] = (tampered[20]! + 1) & 0xff;
    const r = verifyIntegrity(tampered, EXPECTED);
    expect(r.hashValid).toBe(false);
    expect(r.computedHash).not.toBe(EXPECTED);
  });

  test("hashValid=false when the expected hash differs by case (hex must be lowercase)", () => {
    expect(verifyIntegrity(STORED, EXPECTED.toUpperCase()).hashValid).toBe(false);
  });

  test("accepts a string payload as UTF-8", () => {
    const asString = new TextDecoder().decode(STORED);
    expect(verifyIntegrity(asString, EXPECTED).hashValid).toBe(true);
  });
});
