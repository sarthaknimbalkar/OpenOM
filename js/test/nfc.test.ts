import { describe, expect, test } from "vitest";
import { createHash } from "node:crypto";
import { canonicalize } from "../src/canonicalize.js";

function sha256Hex(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * §C.1 [OM-CANON-008] — every string value and member name MUST be
 * NFC-normalized before canonicalization. Worked hashes are from the spec.
 */
describe("[OM-CANON-008] NFC normalization on the Producer path", () => {
  const nfcCafe = "café"; // é = U+00E9 (composed)
  const nfdCafe = "café"; // e + U+0301 combining acute (decomposed)
  const expectedNfcSha =
    "851b8c23eb02709cb52f013fff5215d8b1d836fa2283fbf8e7c35dbbc5a48ddf";

  test("NFC input canonicalizes to the NFC hash", () => {
    expect(sha256Hex(canonicalize({ tenantEntity: nfcCafe }))).toBe(expectedNfcSha);
  });

  test("NFD input is normalized to NFC → same bytes and hash", () => {
    const nfdBytes = canonicalize({ tenantEntity: nfdCafe });
    const nfcBytes = canonicalize({ tenantEntity: nfcCafe });
    expect(new TextDecoder().decode(nfdBytes)).toBe(new TextDecoder().decode(nfcBytes));
    expect(sha256Hex(nfdBytes)).toBe(expectedNfcSha);
  });

  test("NFD member names are normalized to NFC", () => {
    const nfd = canonicalize({ [nfdCafe]: 1 });
    const nfc = canonicalize({ [nfcCafe]: 1 });
    expect(new TextDecoder().decode(nfd)).toBe(new TextDecoder().decode(nfc));
  });
});
