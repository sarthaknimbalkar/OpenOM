import { describe, expect, test } from "vitest";
import { createHash } from "node:crypto";
import { canonicalize } from "../src/canonicalize.js";

/**
 * Known-answer vectors anchored to the spec's hand-worked §C.5 examples
 * (om-standard-handoff-v4-updated.md). These hashes are implementation-
 * independent oracles: the implementation must reproduce them, not the
 * other way around ([OM-VEC-003]).
 */

function sha256Hex(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

describe("§C.5 Example 1 — key sorting + whitespace removal", () => {
  const value = { b: 2, a: 1 };
  const expectedJcs = '{"a":1,"b":2}';
  const expectedSha = "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777";

  test("produces sorted, whitespace-free JCS bytes", () => {
    const bytes = canonicalize(value);
    expect(new TextDecoder().decode(bytes)).toBe(expectedJcs);
    expect(bytes.length).toBe(13);
  });

  test("reproduces the §C.5 Example 1 SHA-256", () => {
    expect(sha256Hex(canonicalize(value))).toBe(expectedSha);
  });
});

describe("§C.5 Example 2 — member ordering by UTF-16 code unit", () => {
  // "😀" (U+1F600 → surrogate D83D DE00) must sort BEFORE "￿" (U+FFFF):
  // code-unit ordering, not code-point. A code-point sorter forks here.
  const value = { "￿": "bmp-max", "\u{1F600}": "grinning", Z: 1, a: 2 };
  const expectedJcs = '{"Z":1,"a":2,"\u{1F600}":"grinning","￿":"bmp-max"}';
  const expectedSha = "856d9d6d59d4a593c79e78e3609435b72487f44e70bf0ea03d16eb2bab0aba31";

  test("sorts by UTF-16 code unit and reproduces the SHA-256", () => {
    const bytes = canonicalize(value);
    expect(new TextDecoder().decode(bytes)).toBe(expectedJcs);
    expect(bytes.length).toBe(47);
    expect(sha256Hex(bytes)).toBe(expectedSha);
  });
});

describe("§C.5 Example 3 — number normalization", () => {
  const value = {
    capRate: 0.0625,
    askingPrice: 1850000,
    noi: 115625,
    rentPSF: 12.7,
    escalationFromPrior: 0.1,
  };
  const expectedJcs =
    '{"askingPrice":1850000,"capRate":0.0625,"escalationFromPrior":0.1,"noi":115625,"rentPSF":12.7}';
  const expectedSha = "3a47e6986d2df5054d4d833871b13781e9edf14ff15b1a3a31a4d2b6b5db6288";

  test("normalizes numbers and reproduces the SHA-256", () => {
    const bytes = canonicalize(value);
    expect(new TextDecoder().decode(bytes)).toBe(expectedJcs);
    expect(bytes.length).toBe(94);
    expect(sha256Hex(bytes)).toBe(expectedSha);
  });
});
