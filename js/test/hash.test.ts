import { describe, expect, test } from "vitest";
import { payloadHash } from "../src/hash.js";

/**
 * §C.3 [OM-CANON-016] integrity-hash preimage + §C.5 Example 4.
 * payloadHash = "sha256:" + lowercase_hex(SHA-256(JCS(P without meta.signature))).
 * meta.signature is REMOVED from the preimage (absent, not null).
 */
describe("[OM-CANON-016] integrity hash — §C.5 Example 4", () => {
  const base = {
    specVersion: "0.1",
    assertedDate: "2026-08-15",
    deal: { askingPrice: 1850000, capRate: 0.0625, noi: 115625, noiType: "in-place" },
    meta: {
      sourceDocHash:
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      supersedes: null,
    },
  };
  const expected =
    "sha256:aa631ed617b85ac226ef4f6ae97e5387a60fdc51c6e49f42c35034c113ca16f7";

  test("hashes a payload with meta.signature absent", () => {
    expect(payloadHash(base)).toBe(expected);
  });

  test("removes meta.signature from the preimage → same hash as absent", () => {
    const signed = {
      ...base,
      meta: { ...base.meta, signature: { alg: "ed25519", sig: "AAAA" } },
    };
    expect(payloadHash(signed)).toBe(expected);
  });

  test("meta.supersedes IS included in the preimage (changing it changes the hash)", () => {
    const superseding = {
      ...base,
      meta: { ...base.meta, supersedes: "sha256:" + "0".repeat(64) },
    };
    expect(payloadHash(superseding)).not.toBe(expected);
  });
});
