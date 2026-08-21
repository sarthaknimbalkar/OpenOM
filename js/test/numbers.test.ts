import { describe, expect, test } from "vitest";
import { parsePayload } from "../src/parse.js";
import { canonicalize } from "../src/canonicalize.js";

/**
 * §C.2/§C.6 number rules at the raw-text parse boundary.
 * [OM-CANON-013] a token whose integer magnitude exceeds 2^53-1 is silently
 * rounded by binary64 and MUST be rejected (OM-IO-NUMRANGE) - detectable only
 * against the source token, since JSON.parse rounds before we can inspect it.
 * [OM-CANON-019] number-serialization torture cases.
 */
describe("[OM-CANON-013] safe-integer rejection at parse", () => {
  test("accepts the max safe integer 9007199254740991", () => {
    expect(parsePayload('{"x":9007199254740991}')).toEqual({ x: 9007199254740991 });
  });

  test("rejects 9007199254740993 (silently rounds to ...992)", () => {
    expect(() => parsePayload('{"x":9007199254740993}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-NUMRANGE" }),
    );
  });

  test("rejects an overflow-to-Infinity token (1e309)", () => {
    expect(() => parsePayload('{"x":1e309}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-NUMRANGE" }),
    );
  });

  test("accepts a large integer inside a string value (not a number token)", () => {
    expect(parsePayload('{"x":"9007199254740993"}')).toEqual({ x: "9007199254740993" });
  });

  test("accepts ordinary decimals and rates", () => {
    expect(parsePayload('{"capRate":0.0625,"rentPSF":12.70}')).toEqual({
      capRate: 0.0625,
      rentPSF: 12.7,
    });
  });
});

describe("[OM-CANON-015/019] JCS number formatting + safe-value policy", () => {
  const jcs = (v: unknown) => new TextDecoder().decode(canonicalize(v));

  test("negative zero serializes as 0", () => {
    expect(jcs({ x: -0 })).toBe('{"x":0}');
  });

  test("in-range (non-integer) floats match ECMAScript Number::toString", () => {
    expect(jcs({ x: 1e-7 })).toBe('{"x":1e-7}');
    expect(jcs({ x: 1e-6 })).toBe('{"x":0.000001}');
    expect(jcs({ x: 0.0625 })).toBe('{"x":0.0625}');
  });

  test("max safe integer serializes with no exponent", () => {
    expect(jcs({ x: 9007199254740991 })).toBe('{"x":9007199254740991}');
  });

  test("integer-valued numbers beyond 2^53-1 are rejected (parity with the Python core)", () => {
    for (const big of [1e20, 1e21, 2 ** 53]) {
      expect(() => canonicalize({ x: big })).toThrowError(
        expect.objectContaining({ code: "OM-IO-NUMRANGE" }),
      );
    }
  });
});
