import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PDFDocument, PDFName, PDFDict, PDFArray, PDFRef } from "pdf-lib";
import { embedPayload } from "../src/embed.js";
import { readPayloadFromBytes } from "../src/read.js";
import { payloadHash, preimageBytes } from "../src/hash.js";

const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const validStnl = JSON.parse(
  readFileSync(join(specDir, "samples", "valid-stnl.json"), "utf8"),
) as Record<string, unknown>;

async function blankPdf(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.addPage([612, 792]);
  return doc.save();
}

/**
 * §D embed (assumption A: store the signature-stripped preimage; omspec:
 * payloadHash = payloadHash(payload)) proven by the embed → read round-trip,
 * plus the OM-EMB-007 shared-stream `/EF` invariant.
 */
describe("embedPayload", () => {
  test("embed → read round-trips and verifies (hashValid true)", async () => {
    const out = await embedPayload(await blankPdf(), validStnl);
    const r = await readPayloadFromBytes(out);
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
    expect(r.payloadHash).toBe(payloadHash(validStnl));
  });

  test("stores exactly the preimage bytes (OM-CANON-005)", async () => {
    const out = await embedPayload(await blankPdf(), validStnl);
    const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
    const pdf = await pdfjs.getDocument({ data: out.slice(), verbosity: 0 }).promise;
    const att = await pdf.getAttachments();
    await pdf.destroy();
    const stored = att!["om.json"]!.content as Uint8Array;
    expect(Array.from(stored)).toEqual(Array.from(preimageBytes(validStnl)));
  });

  test("/EF has both /F and /UF referencing the SAME stream (OM-EMB-007)", async () => {
    const out = await embedPayload(await blankPdf(), validStnl);
    const doc = await PDFDocument.load(out);
    const af = doc.catalog.lookup(PDFName.of("AF"), PDFArray);
    const filespec = doc.context.lookup(af.get(0), PDFDict);
    const ef = filespec.lookup(PDFName.of("EF"), PDFDict);
    const fRef = ef.get(PDFName.of("F"));
    const ufRef = ef.get(PDFName.of("UF"));
    expect(fRef).toBeInstanceOf(PDFRef);
    expect(ufRef).toBeInstanceOf(PDFRef);
    expect((ufRef as PDFRef).tag).toBe((fRef as PDFRef).tag);
  });

  test("writes the omspec XMP marker (payloadHash) so detection works", async () => {
    const out = await embedPayload(await blankPdf(), validStnl);
    const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
    const pdf = await pdfjs.getDocument({ data: out.slice(), verbosity: 0 }).promise;
    const md = await pdf.getMetadata();
    await pdf.destroy();
    expect(md.metadata!.get("omspec:payloadhash")).toBe(payloadHash(validStnl));
    expect(md.metadata!.get("omspec:specversion")).toBe("0.1");
  });

  test("writes the PDF/A extension schema describing the omspec namespace (#2)", async () => {
    const out = await embedPayload(await blankPdf(), validStnl);
    const xmp = new TextDecoder().decode(out); // Metadata stream is uncompressed UTF-8
    expect(xmp).toContain("http://www.aiim.org/pdfa/ns/extension/");
    expect(xmp).toContain(
      "<pdfaSchema:namespaceURI>https://openom.app/ns/0.1#</pdfaSchema:namespaceURI>",
    );
    expect(xmp).toContain("<pdfaSchema:prefix>omspec</pdfaSchema:prefix>");
    for (const name of ["specName", "payloadHash", "assertedDate", "supersedes"]) {
      expect(xmp).toContain(`<pdfaProperty:name>${name}</pdfaProperty:name>`);
    }
  });
});

describe("embedPayload - idempotent re-embed ([OM-XMP-004], cross-impl parity)", () => {
  test("re-embed replaces (never stacks a second om.json) and reads the new payload", async () => {
    const first = await embedPayload(await blankPdf(), validStnl);

    const reprice = JSON.parse(JSON.stringify(validStnl)) as Record<string, unknown>;
    (reprice.deal as Record<string, unknown>).askingPrice =
      Number((validStnl.deal as Record<string, unknown>).askingPrice) + 500;
    (reprice.meta as Record<string, unknown>).supersedes = payloadHash(validStnl);

    const second = await embedPayload(first, reprice);

    // exactly one embedded file remains in /AF
    const doc = await PDFDocument.load(second);
    const af = doc.catalog.lookup(PDFName.of("AF"), PDFArray);
    expect(af.size()).toBe(1);

    // and it reads back as the NEW payload, hash-valid
    const r = await readPayloadFromBytes(second);
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
    expect((r.payload!.deal as Record<string, unknown>).askingPrice).toBe(
      Number((validStnl.deal as Record<string, unknown>).askingPrice) + 500,
    );
    expect((r.payload!.meta as Record<string, unknown>).supersedes).toBe(payloadHash(validStnl));
  });
});
