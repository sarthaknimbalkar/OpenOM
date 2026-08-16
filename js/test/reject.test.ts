import { describe, expect, test } from "vitest";
import { canonicalize } from "../src/canonicalize.js";
import { OmIoError } from "../src/errors.js";

/**
 * §C.1/§C.2 rejection rules on the canonicalization (Producer) path.
 * [OM-CANON-010] structural preconditions; [OM-CANON-013] non-representable
 * numbers; [OM-CANON-014] non-finite numbers.
 */
describe("[OM-CANON-014] reject non-finite numbers", () => {
  test.each([NaN, Infinity, -Infinity])("rejects %s with OM-IO-NUMRANGE", (n) => {
    expect(() => canonicalize({ x: n })).toThrowError(
      expect.objectContaining({ code: "OM-IO-NUMRANGE" }),
    );
    expect(() => canonicalize({ x: n })).toThrowError(OmIoError);
  });
});

describe("[OM-CANON-013/015] value-level number representability", () => {
  test("accepts the max safe integer 2^53-1", () => {
    expect(() => canonicalize({ x: 9007199254740991 })).not.toThrow();
  });

  test("rejects integer-valued numbers beyond 2^53-1 (parity with the Python core)", () => {
    // Unified [OM-CANON-013] policy: any integer-valued number with |v| > 2^53-1 is rejected,
    // whether written 1000...0 or 1e21. No CRE figure approaches 2^53, and accepting it would
    // fork from the Python core (which rejects). Non-integer floats (1e-7, 0.0625) are fine.
    for (const big of [1e20, 1e21, 2 ** 53]) {
      expect(() => canonicalize({ x: big })).toThrowError(
        expect.objectContaining({ code: "OM-IO-NUMRANGE" }),
      );
    }
  });
});

describe("[OM-CANON-010] structural preconditions", () => {
  test.each([[[1, 2]], ["scalar"], [42], [null]])(
    "rejects non-object top-level payload %j",
    (v) => {
      expect(() => canonicalize(v)).toThrowError(
        expect.objectContaining({ code: "OM-IO-STRUCTURE" }),
      );
    },
  );

  test("accepts a top-level object", () => {
    expect(() => canonicalize({ ok: true })).not.toThrow();
  });
});
