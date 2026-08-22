import { describe, expect, test } from "vitest";
import { pdfHasSignature } from "../src/signature.js";

const enc = (s: string): Uint8Array => new TextEncoder().encode(s);

describe("pdfHasSignature ([M1])", () => {
  test("detects a signature by its /ByteRange", () => {
    expect(pdfHasSignature(enc("%PDF-1.6\n<< /Type /Sig /ByteRange [0 100 200 300] >>"))).toBe(
      true,
    );
  });
  test("detects the adbe.pkcs7 / ETSI.CAdES handlers and DocMDP", () => {
    expect(pdfHasSignature(enc("/SubFilter /adbe.pkcs7.detached"))).toBe(true);
    expect(pdfHasSignature(enc("/SubFilter /ETSI.CAdES.detached"))).toBe(true);
    expect(pdfHasSignature(enc("/TransformMethod /DocMDP"))).toBe(true);
  });
  test("returns false for an unsigned PDF", () => {
    expect(pdfHasSignature(enc("%PDF-1.7\n<< /Type /Catalog /Pages 2 0 R >>"))).toBe(false);
  });
});
