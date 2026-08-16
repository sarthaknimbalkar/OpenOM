import { describe, expect, test } from "vitest";
import { parsePayload } from "../src/parse.js";
import { OmIoError } from "../src/errors.js";

/**
 * §C.1 [OM-CANON-009/010] + §J hardened parse boundary. A JS object cannot
 * itself carry duplicate keys, so duplicate/bad-UTF8 detection must happen
 * against the raw text/bytes before parsing.
 */
describe("[OM-CANON-009] duplicate member names → OM-IO-DUPKEY", () => {
  test("rejects a duplicate key at the top level", () => {
    expect(() => parsePayload('{"a":1,"a":2}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-DUPKEY" }),
    );
  });

  test("rejects a duplicate key in a nested object", () => {
    expect(() => parsePayload('{"deal":{"noi":1,"noi":2}}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-DUPKEY" }),
    );
  });

  test("rejects keys that collide only after NFC normalization", () => {
    // "café" composed (U+00E9) vs decomposed (e + U+0301) — equal after NFC.
    expect(() => parsePayload('{"café":1,"café":2}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-DUPKEY" }),
    );
  });

  test("accepts distinct keys and repeated keys across sibling objects", () => {
    const v = parsePayload('{"x":{"a":1},"y":{"a":2}}');
    expect(v).toEqual({ x: { a: 1 }, y: { a: 2 } });
  });

  test("does not treat a string value that looks like a key as a duplicate", () => {
    const v = parsePayload('{"a":"a","b":"a"}');
    expect(v).toEqual({ a: "a", b: "a" });
  });

  test("ignores ':' and '{' that appear INSIDE string values", () => {
    const v = parsePayload('{"url":"https://x/{a}:b","url2":"c:d"}');
    expect(v).toEqual({ url: "https://x/{a}:b", url2: "c:d" });
  });

  test("ignores an escaped quote inside a value that precedes a ':'", () => {
    const v = parsePayload('{"a":"he said \\":\\"","b":2}');
    expect(v).toEqual({ a: 'he said ":"', b: 2 });
  });

  test("detects a duplicate key written with a \\u escape (NFC-decoded)", () => {
    // "café" (composed) vs decomposed "café" — same after NFC → duplicate.
    expect(() => parsePayload('{"caf\\u00e9":1,"café":2}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-DUPKEY" }),
    );
  });

  test("does not confuse a key inside an array element's object with the outer object", () => {
    const v = parsePayload('{"a":1,"list":[{"a":2},{"a":3}]}');
    expect(v).toEqual({ a: 1, list: [{ a: 2 }, { a: 3 }] });
  });
});

describe("[OM-CANON-010] malformed Unicode → OM-IO-BADUTF8", () => {
  test("rejects an unpaired surrogate from a \\u escape", () => {
    expect(() => parsePayload('{"a":"\\uD83D"}')).toThrowError(
      expect.objectContaining({ code: "OM-IO-BADUTF8" }),
    );
  });

  test("rejects malformed UTF-8 bytes", () => {
    // 0xFF is never valid UTF-8.
    const bad = new Uint8Array([0x7b, 0x22, 0x61, 0x22, 0x3a, 0xff, 0x7d]);
    expect(() => parsePayload(bad)).toThrowError(
      expect.objectContaining({ code: "OM-IO-BADUTF8" }),
    );
  });

  test("accepts a valid paired surrogate (astral char)", () => {
    const v = parsePayload('{"a":"😀"}');
    expect(v).toEqual({ a: "\u{1F600}" });
  });
});

describe("[OM-CANON-010] structural preconditions", () => {
  test("rejects a non-object top-level", () => {
    expect(() => parsePayload("[1,2]")).toThrowError(
      expect.objectContaining({ code: "OM-IO-STRUCTURE" }),
    );
  });

  test("rejects invalid JSON", () => {
    expect(() => parsePayload("{not json}")).toThrowError(OmIoError);
  });
});
