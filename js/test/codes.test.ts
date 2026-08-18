import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { REQUIREMENT } from "../src/consistency.js";

// #151: drift-lock the JS consistency REQUIREMENT map to the canonical spec/codes.json registry, so a
// warning/info code's requirement can't diverge between the two cores (Python side: test_codes.py).
const registry = JSON.parse(
  readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec", "codes.json"),
    "utf8",
  ),
) as { codes: Record<string, { requirement: string; severity: string }> };

describe("finding-code registry drift-lock (#151)", () => {
  test("every consistency REQUIREMENT entry matches spec/codes.json", () => {
    const mismatches: string[] = [];
    for (const [code, req] of Object.entries(REQUIREMENT)) {
      const canon = registry.codes[code];
      if (!canon) mismatches.push(`${code}: absent from spec/codes.json`);
      else if (canon.requirement !== req)
        mismatches.push(`${code}: ${req} != ${canon.requirement}`);
    }
    expect(mismatches).toEqual([]);
  });
});
