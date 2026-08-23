import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { OM_CODES, type OmCode } from "../src/codes.js";

const jsDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const specCodes = JSON.parse(readFileSync(join(jsDir, "..", "spec", "codes.json"), "utf8"))
  .codes as Record<string, unknown>;

/** [Mi19] OM_CODES + the OmCode union are generated from spec/codes.json — drift-locked so the
 *  exported registry can never diverge from the canonical source both cores drift-lock to. */
describe("[Mi19] OM_CODES registry", () => {
  test("OM_CODES deep-equals the committed spec/codes.json codes", () => {
    expect(OM_CODES).toEqual(specCodes);
  });

  test("every code is self-describing (message + requirement + severity)", () => {
    for (const [code, e] of Object.entries(OM_CODES)) {
      expect(e.message, code).toBeTruthy();
      expect(e.requirement, code).toMatch(/^OM-/);
      expect(["error", "warning", "info"]).toContain(e.severity);
    }
  });

  test("regenerating reproduces the committed src/codes.ts exactly", () => {
    const committed = readFileSync(join(jsDir, "src", "codes.ts"), "utf8");
    execFileSync("node", ["scripts/gen-codes.mjs"], { cwd: jsDir, stdio: "ignore" });
    expect(readFileSync(join(jsDir, "src", "codes.ts"), "utf8")).toBe(committed);
  });

  test("the OmCode union is usable as a type", () => {
    const c: OmCode = "OMV-E002";
    expect(OM_CODES[c]?.severity).toBe("error");
  });
});
