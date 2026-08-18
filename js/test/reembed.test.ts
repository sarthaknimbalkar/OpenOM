import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PDFDocument } from "pdf-lib";
import { embedPayload } from "../src/embed.js";
import { reembedWarnings } from "../src/reembed.js";
import { readMarkerProp } from "../src/read.js";
import { integrityHashOfBytes } from "../src/verify.js";

/**
 * OMW-W051 re-embed provenance warning — parity with the Python core's reembed_warnings.
 * A reprice whose assertedDate precedes the payload it supersedes warns (never blocks).
 * Note: assertedDate is part of the payload, so a reprice changes both the date and the hash.
 */
const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const sample = (name: string) =>
  JSON.parse(readFileSync(join(specDir, "samples", `${name}.json`), "utf8")) as Record<
    string,
    unknown
  >;

async function blankPdf(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.addPage([612, 792]);
  return doc.save();
}

function reprice(base: Record<string, unknown>, assertedDate: string): Record<string, unknown> {
  return {
    ...base,
    assertedDate,
    deal: { ...(base.deal as Record<string, unknown>), askingPrice: 1795000 },
  };
}

describe("reembedWarnings (OMW-W051)", () => {
  const v1 = (): Record<string, unknown> => ({
    ...sample("valid-stnl"),
    assertedDate: "2026-08-15",
  });

  test("warns when a reprice goes backwards in time", async () => {
    const prior = await embedPayload(await blankPdf(), v1());
    const warnings = await reembedWarnings(prior, reprice(v1(), "2026-07-01"));
    expect(warnings.some((w) => w.code === "OMW-W051")).toBe(true);
  });

  test("no warning for a forward-dated reprice", async () => {
    const prior = await embedPayload(await blankPdf(), v1());
    expect(await reembedWarnings(prior, reprice(v1(), "2026-09-01"))).toEqual([]);
  });

  test("no warning for an identical re-embed (same payload, not a reprice)", async () => {
    const prior = await embedPayload(await blankPdf(), v1());
    expect(await reembedWarnings(prior, v1())).toEqual([]);
  });

  test("no warning when the prior PDF has no marker", async () => {
    expect(await reembedWarnings(await blankPdf(), v1())).toEqual([]);
  });
});

describe("#166: sourceDocHash carried across reprices (parity with Python #5)", () => {
  test("first embed records the hash of the source PDF; a reprice preserves it", async () => {
    const src = await blankPdf();
    const origin = integrityHashOfBytes(src);

    const first = await embedPayload(src, sample("valid-stnl"));
    expect(await readMarkerProp(first, "sourceDocHash")).toBe(origin);

    // A reprice (different payload) must keep the ORIGINAL sourceDocHash, not hash the embedded PDF.
    const second = await embedPayload(first, reprice(sample("valid-stnl"), "2026-08-19"));
    expect(await readMarkerProp(second, "sourceDocHash")).toBe(origin);
    expect(await readMarkerProp(second, "sourceDocHash")).not.toBe(integrityHashOfBytes(first));
  });
});
