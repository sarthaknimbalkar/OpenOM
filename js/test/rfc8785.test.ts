import { describe, expect, test } from "vitest";
import { canonicalize } from "../src/canonicalize.js";

// #134: independent RFC 8785 anchor for the TS core (mirror of core/tests/test_rfc8785.py). Vectors are
// hand-derived from the RFC rules - key sort by UTF-16 code unit, minimal string escaping, ECMAScript
// Number.toString, array order preserved, NFC non-ASCII emitted raw - so they prove canonicalize is
// CORRECT, not merely equal to the Python core. Only openOM's accepted number range is used.
const dec = new TextDecoder();
const CONTROLS = String.fromCharCode(0x01) + String.fromCharCode(0x1f);
const V: [Record<string, unknown>, string][] = [
  [{ b: 1, a: 2, c: 3 }, '{"a":2,"b":1,"c":3}'],
  [{ z: { y: 1, x: 2 } }, '{"z":{"x":2,"y":1}}'],
  [{ arr: [3, 1, 2] }, '{"arr":[3,1,2]}'],
  [{ a: true, b: false, c: null }, '{"a":true,"b":false,"c":null}'],
  [{ s: 'a"b\\c' }, '{"s":"a\\"b\\\\c"}'],
  [{ s: "tab\tnl\n" }, '{"s":"tab\\tnl\\n"}'],
  [{ s: CONTROLS }, '{"s":"\\u0001\\u001f"}'],
  [{ s: "é" }, '{"s":"é"}'],
  [{ s: "中文" }, '{"s":"中文"}'],
  [{ n: 4.5 }, '{"n":4.5}'],
  [{ n: 100 }, '{"n":100}'],
  [{ n: -0.0 }, '{"n":0}'],
  [{ n: 0.002 }, '{"n":0.002}'],
  [{ n: 2 ** 53 - 1 }, '{"n":9007199254740991}'],
];

describe("RFC 8785 anchor - TS canonicalize is correct, not just self-consistent (#134)", () => {
  for (const [value, expected] of V) {
    test(`canonicalize ${expected}`, () => {
      expect(dec.decode(canonicalize(value))).toBe(expected);
    });
  }
});
