import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PDFArray, PDFDict, PDFDocument, PDFName } from "pdf-lib";
import { embedPayload } from "../src/embed.js";
import { readPayloadFromBytes } from "../src/read.js";

const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const fixtures = join(dirname(fileURLToPath(import.meta.url)), "fixtures");
const payload = JSON.parse(readFileSync(join(specDir, "samples", "valid-stnl.json"), "utf8")) as Record<
  string,
  unknown
>;

/** Structural fingerprint an embed must preserve ([OM-DoD-001]): pages, outline nodes, link annots. */
async function structure(bytes: Uint8Array): Promise<{ pages: number; bookmarks: number; links: number }> {
  const doc = await PDFDocument.load(bytes, { throwOnInvalidObject: false, updateMetadata: false });
  const pages = doc.getPageCount();

  let bookmarks = 0;
  const outlines = doc.catalog.lookup(PDFName.of("Outlines"));
  if (outlines instanceof PDFDict) {
    let node = outlines.lookup(PDFName.of("First"));
    while (node instanceof PDFDict) {
      bookmarks++;
      node = node.lookup(PDFName.of("Next"));
    }
  }

  let links = 0;
  for (const page of doc.getPages()) {
    const annots = page.node.lookup(PDFName.of("Annots"));
    if (annots instanceof PDFArray) {
      for (let i = 0; i < annots.size(); i++) {
        const a = doc.context.lookup(annots.get(i));
        if (a instanceof PDFDict && a.lookup(PDFName.of("Subtype")) === PDFName.of("Link")) links++;
      }
    }
  }
  return { pages, bookmarks, links };
}

describe("embedPayload — non-destructive ([OM-DoD-001], #105)", () => {
  test("preserves pages, bookmarks, and link annotations on a structured PDF", async () => {
    const src = new Uint8Array(readFileSync(join(fixtures, "structured.pdf")));
    const before = await structure(src);
    expect(before).toEqual({ pages: 2, bookmarks: 2, links: 2 }); // the fixture really has these

    const embedded = await embedPayload(src, payload);
    const after = await structure(embedded);
    expect(after).toEqual(before); // nothing structural lost or added (besides the om.json attachment)

    const read = await readPayloadFromBytes(embedded);
    expect(read.state).toBe("present"); // and the payload round-trips
    expect(read.verification.hashValid).toBe(true);
  });
});
