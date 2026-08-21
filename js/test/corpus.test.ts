import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { consistencyFindings } from "../src/consistency.js";

/**
 * CROSS-IMPLEMENTATION consistency conformance (#42). The JS engine runs the SAME
 * fixtures/seeded_defects/manifest.json the Python gate ([OM-DoD-002], core/tests/
 * test_consistency.py) runs - one corpus, both engines - so every §H warning/info code is
 * reproduced identically and the parity is vector-locked, not merely mirrored by hand.
 */
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const corpusDir = join(repoRoot, "fixtures", "seeded_defects");

interface Mutation {
  path: string;
  value?: unknown;
  delete?: boolean;
}
interface Case {
  name: string;
  expect: string[];
  expectInfo?: string[];
  asOf?: string;
  selfSupersede?: boolean;
  mutations: Mutation[];
}
interface Manifest {
  base: string;
  cases: Case[];
}

const manifest = JSON.parse(readFileSync(join(corpusDir, "manifest.json"), "utf8")) as Manifest;
const base = JSON.parse(readFileSync(join(repoRoot, manifest.base), "utf8")) as Record<
  string,
  unknown
>;

function ref(doc: unknown, parts: string[]): Record<string, unknown> | unknown[] {
  let node: unknown = doc;
  for (const part of parts) {
    node = Array.isArray(node) ? node[Number(part)] : (node as Record<string, unknown>)[part];
  }
  return node as Record<string, unknown> | unknown[];
}

function applyCase(c: Case): Record<string, unknown> {
  const payload = structuredClone(base);
  for (const mut of c.mutations) {
    const parts = mut.path.replace(/^\//, "").split("/");
    const parent = ref(payload, parts.slice(0, -1));
    const key = parts[parts.length - 1]!;
    if (mut.delete) {
      if (Array.isArray(parent)) parent.splice(Number(key), 1);
      else delete parent[key];
    } else if (Array.isArray(parent)) {
      parent[Number(key)] = mut.value;
    } else {
      parent[key] = mut.value;
    }
  }
  return payload;
}

describe("cross-impl consistency conformance (shared seeded-defect corpus with the Python gate)", () => {
  for (const c of manifest.cases) {
    test(`${c.name} reproduces ${[...c.expect, ...(c.expectInfo ?? [])].join(", ") || "no codes"}`, async () => {
      const payload = applyCase(c);
      if (c.selfSupersede) {
        const { payloadHash } = await import("../src/hash.js");
        const stripped = structuredClone(payload);
        delete (stripped.meta as Record<string, unknown>).supersedes;
        (payload.meta as Record<string, unknown>).supersedes = payloadHash(stripped);
      }
      const { warnings, info } = consistencyFindings(
        payload,
        undefined,
        c.asOf ? { asOf: c.asOf } : {},
      );
      const warnCodes = new Set(warnings.map((w) => w.code));
      const infoCodes = new Set(info.map((i) => i.code));
      for (const code of c.expect) expect(warnCodes).toContain(code);
      for (const code of c.expectInfo ?? []) expect(infoCodes).toContain(code);
    });
  }
});
