import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PDFDocument, PDFName, PDFString, PDFHexString } from "pdf-lib";
import { decryptPdf } from "../src/decrypt.js";
import { decryptPdf as decryptPdfFromIndex } from "../src/index.js";
import { embedPayload } from "../src/embed.js";
import { readPayloadFromBytes } from "../src/read.js";
import { extractPageText } from "../src/text.js";

const fixDir = join(dirname(fileURLToPath(import.meta.url)), "fixtures");
const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const known = JSON.parse(readFileSync(join(fixDir, "enc-fixtures.json"), "utf8")) as {
  text: string;
  bookmark: string;
};
const payload = JSON.parse(
  readFileSync(join(specDir, "samples", "valid-stnl.json"), "utf8"),
) as Record<string, unknown>;
const fix = (name: string): Uint8Array => new Uint8Array(readFileSync(join(fixDir, name)));

/** First outline title of a decrypted PDF — proves STRING decryption (bookmark titles are encrypted). */
async function firstOutlineTitle(bytes: Uint8Array): Promise<string | null> {
  const doc = await PDFDocument.load(bytes);
  const outlines = doc.catalog.lookup(PDFName.of("Outlines"));
  if (!outlines) return null;
  const first = (outlines as import("pdf-lib").PDFDict).lookup(PDFName.of("First"));
  if (!first) return null;
  const title = (first as import("pdf-lib").PDFDict).lookup(PDFName.of("Title"));
  return title instanceof PDFString || title instanceof PDFHexString ? title.decodeText() : null;
}

describe("decryptPdf — V4/R4 AES-128 (#4)", () => {
  test("decrypts an empty-password AES-128 PDF (stream + string)", async () => {
    const out = await decryptPdf(fix("enc-aes128.pdf"));
    expect(out).not.toBeNull();
    // Loading WITHOUT ignoreEncryption proves /Encrypt is gone and objects are plaintext.
    await expect(PDFDocument.load(out!)).resolves.toBeDefined();
    const text = (await extractPageText(out!)).pages[0]?.text ?? "";
    expect(text).toContain(known.text);
    expect(await firstOutlineTitle(out!)).toBe(known.bookmark);
  });

  test("the decrypted AES-128 PDF accepts an openOM embed round-trip", async () => {
    const out = await decryptPdf(fix("enc-aes128.pdf"));
    const embedded = await embedPayload(out!, payload);
    const r = await readPayloadFromBytes(embedded);
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
  });
});

describe("decryptPdf — V5/R6 AES-256 (#4)", () => {
  test("decrypts an empty-password AES-256 PDF (stream + string)", async () => {
    const out = await decryptPdf(fix("enc-aes256.pdf"));
    expect(out).not.toBeNull();
    await expect(PDFDocument.load(out!)).resolves.toBeDefined();
    const text = (await extractPageText(out!)).pages[0]?.text ?? "";
    expect(text).toContain(known.text);
    expect(await firstOutlineTitle(out!)).toBe(known.bookmark);
  });

  test("the decrypted AES-256 PDF accepts an openOM embed round-trip", async () => {
    const out = await decryptPdf(fix("enc-aes256.pdf"));
    const embedded = await embedPayload(out!, payload);
    const r = await readPayloadFromBytes(embedded);
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
  });
});

describe("decryptPdf — out-of-scope ⇒ null (#4 fallback to #107)", () => {
  test("returns null for an RC4-encrypted PDF", async () => {
    expect(await decryptPdf(fix("enc-rc4.pdf"))).toBeNull();
  });

  test("returns null for a genuinely password-protected PDF (empty password fails /U)", async () => {
    expect(await decryptPdf(fix("encrypted-userpw.pdf"))).toBeNull();
  });

  test("returns null for a non-encrypted PDF (no /Encrypt)", async () => {
    expect(await decryptPdf(fix("structured.pdf"))).toBeNull();
  });

  test("returns null for garbage bytes", async () => {
    expect(await decryptPdf(new Uint8Array([1, 2, 3, 4]))).toBeNull();
  });

  test("decryptPdf is exported from the package index", () => {
    expect(typeof decryptPdfFromIndex).toBe("function");
  });
});
