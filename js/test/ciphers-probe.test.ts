import { describe, expect, test } from "vitest";
import { cbc } from "@noble/ciphers/aes.js";

// Guardrail (not product logic): locks the exact @noble/ciphers CBC API that decrypt.ts (#4) depends on.
// Verified against @noble/ciphers@2.3.0: `cbc(key, iv).decrypt(ct)` strips PKCS#7; `cbc(key, iv,
// { disablePadding: true })` does whole-block no-padding CBC (needed for R6 /UE + Algorithm 2.B); a
// wrong key throws on a padded decrypt - decryptPdf's null-guard relies on that throw.
const k16 = new Uint8Array(16).fill(0x01);
const k32 = new Uint8Array(32).fill(0x02);
const iv = new Uint8Array(16).fill(0x03);

describe("@noble/ciphers CBC API (#4 decrypt dependency)", () => {
  test("padded round-trip for AES-128 and AES-256", () => {
    const pt = new TextEncoder().encode("hello openOM padded");
    for (const key of [k16, k32]) {
      const ct = cbc(key, iv).encrypt(pt);
      expect(cbc(key, iv).decrypt(ct)).toEqual(pt);
    }
  });

  test("no-padding round-trip on a whole-block input", () => {
    const pt = new Uint8Array(32).fill(0x09);
    const ct = cbc(k32, iv, { disablePadding: true }).encrypt(pt);
    expect(ct.length).toBe(32);
    expect(cbc(k32, iv, { disablePadding: true }).decrypt(ct)).toEqual(pt);
  });

  test("a wrong key throws on a padded decrypt (the null-guard depends on this)", () => {
    const ct = cbc(k16, iv).encrypt(new TextEncoder().encode("x"));
    expect(() => cbc(new Uint8Array(16).fill(0x07), iv).decrypt(ct)).toThrow();
  });
});
