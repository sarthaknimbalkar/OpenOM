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

  test("accepts large-magnitude representable doubles (1e21) — NOT rejected here", () => {
    // Regression guard: 1e21 is integer-VALUED but exactly representable and
    // serializes as 1e+21 ([OM-CANON-015]); value-level rejection would be a bug.
    // Silent integer-precision loss is caught at the parse boundary instead.
    expect(() => canonicalize({ x: 1e21 })).not.toThrow();
    expect(() => canonicalize({ x: 1e20 })).not.toThrow();
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
