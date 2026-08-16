import { describe, expect, test } from "vitest";
import { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES } from "../src/parse.js";

/**
 * §J [OM-SEC-002] decompression/size guard. A payload larger than the cap is
 * rejected before parsing so a hostile input cannot exhaust memory.
 */
describe("[OM-SEC-002] payload size cap → OM-IO-BOMB", () => {
  test("exposes a documented default cap", () => {
    expect(DEFAULT_MAX_PAYLOAD_BYTES).toBe(5 * 1024 * 1024);
  });

  test("rejects input over the default cap (bytes)", () => {
    const oversized = new Uint8Array(DEFAULT_MAX_PAYLOAD_BYTES + 1);
    expect(() => parsePayload(oversized)).toThrowError(
      expect.objectContaining({ code: "OM-IO-BOMB" }),
    );
  });

  test("honours a caller-supplied maxBytes", () => {
    const text = `{"a":"${"x".repeat(100)}"}`;
    expect(() => parsePayload(text, { maxBytes: 16 })).toThrowError(
      expect.objectContaining({ code: "OM-IO-BOMB" }),
    );
  });

  test("accepts input at exactly the cap", () => {
    // 16-byte body: {"a":"xxxxxxxx"} is 16 bytes.
    const text = '{"a":"xxxxxxxx"}';
    expect(new TextEncoder().encode(text).length).toBe(16);
    expect(parsePayload(text, { maxBytes: 16 })).toEqual({ a: "xxxxxxxx" });
  });
});
