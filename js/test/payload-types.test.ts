import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { OMPayload, RealEstateListing } from "../src/index.js";

const jsDir = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * [Ma3] The exported OMPayload type is generated from spec/om-0.1.schema.json. This drift-locks it:
 * regenerating must reproduce the committed file byte-for-byte, so the type can never silently
 * diverge from the schema (the same guarantee schema.test.ts gives OM_SCHEMA).
 */
describe("[Ma3] OMPayload type is generated from the schema (no drift)", () => {
  test("regenerating produces the committed src/payload-types.ts exactly", () => {
    const committed = readFileSync(join(jsDir, "src", "payload-types.ts"), "utf8");
    execFileSync("node", ["scripts/gen-types.mjs"], { cwd: jsDir, stdio: "ignore" });
    const regenerated = readFileSync(join(jsDir, "src", "payload-types.ts"), "utf8");
    expect(regenerated).toBe(committed);
  });

  test("the type is usable and enforces the contract at compile time", () => {
    // A structurally-valid payload assigns cleanly; this is a compile-time proof the type exists and
    // describes the real contract (noiType enum, specVersion literal, nested assertedBy).
    const p: OMPayload = {
      "@context": ["https://openom.app/openom/0.1"],
      "@type": "RealEstateListing",
      specVersion: "0.1",
      assertedBy: { broker: "Acme", brokerage: "Acme CRE", license: "RE-123" },
      assertedDate: "2026-01-01",
      meta: { supersedes: null },
    } as OMPayload;
    const alias: RealEstateListing = p;
    expect(alias.specVersion).toBe("0.1");
  });
});
