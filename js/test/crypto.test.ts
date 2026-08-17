import { describe, expect, test } from "vitest";
import { hmacSha256Hex, sha256Hex } from "../src/crypto.js";

describe("hmacSha256Hex", () => {
  test("matches a known HMAC-SHA256 vector", () => {
    // key "key", msg "The quick brown fox jumps over the lazy dog" (well-published vector)
    expect(hmacSha256Hex("key", "The quick brown fox jumps over the lazy dog")).toBe(
      "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8",
    );
  });

  test("empty key and message (RFC 4231-style)", () => {
    expect(hmacSha256Hex("", "")).toBe(
      "b613679a0814d9ec772f95d778c35fc5ff1697c493715653c6c712144292c5ad",
    );
  });

  test("sha256Hex still works (regression)", () => {
    expect(sha256Hex(new TextEncoder().encode("abc"))).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    );
  });
});
