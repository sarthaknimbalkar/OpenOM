import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, test } from "vitest";
import { canonicalize } from "openom-js";
import { buildoutListingToPayload } from "../../src/author/extract/connectors/buildout.js";

const dec = new TextDecoder();

// The TS half of the mapper differential (the Buildout on-ramp anti-fork). The Python CLI mapper
// (gen_mapper_corpus.py) committed the listing-derived payload subtree for each listing; here the
// extension connector maps the SAME listings and must reproduce it byte-for-byte. This pins the CLI
// bulk path and the extension author path together - they silently forked at a .5 rounding tie before.
const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "spec", "vectors", "mapper");
const lines = (name: string): string[] =>
  readFileSync(join(dir, name), "utf8").split(/\r?\n/).filter(Boolean); // tolerate CRLF checkouts

// Identity fields the CLI adds from flags but the connector leaves for the review gate; excluded from
// the parity contract, which is only the listing-derived mapping.
const IDENTITY = ["assertedBy", "assertedDate", "@context", "@type", "specVersion", "meta"];

describe("mapper differential - TS connector matches the Python CLI mapper", () => {
  test("every listing maps to the same listing-derived payload subtree", () => {
    const listings = lines("listings.jsonl");
    const expected = lines("expected.jsonl");
    expect(listings.length).toBe(expected.length);
    const mismatches: string[] = [];
    for (let i = 0; i < listings.length; i++) {
      const c = JSON.parse(listings[i]!) as { name: string; listing: Record<string, unknown> };
      const p = buildoutListingToPayload(c.listing) as Record<string, unknown>;
      for (const k of IDENTITY) delete p[k];
      const deal = p.deal as Record<string, unknown> | undefined;
      if (deal) {
        delete deal.noiType;
        delete deal.noiAsOfDate;
      }
      const got = dec.decode(canonicalize(p)); // JCS normal form (same normalizer as Python)
      if (got !== expected[i]) mismatches.push(`${c.name}:\n  got  ${got}\n  want ${expected[i]}`);
    }
    expect(mismatches).toEqual([]);
  });
});
