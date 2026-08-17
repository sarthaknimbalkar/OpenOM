// OPT-IN pdf.js decrypt fallback for readPayloadFromBytes ([#106]). pdf.js can decrypt empty-password
// PDFs, but it (a) needs a Worker — unavailable in an MV3 service worker — and (b) is ~1MB. So it is
// NOT bundled into the deterministic read path; callers that want it (Node tooling reading an
// empty-password-encrypted OM) pass this explicitly. In the browser, encrypted OMs simply report the
// `encrypted` state instead. Zero inference.
import { verifyIntegrity } from "./verify.js";
import { parsePayload } from "./parse.js";
import type { ReadResult, ReadVerification } from "./read.js";

/** The shape readPayloadFromBytes accepts as its optional decrypt fallback. */
export type DecryptRead = (pdfBytes: Uint8Array, encrypted: boolean) => Promise<ReadResult>;

const UNVERIFIED: ReadVerification = {
  hashValid: null,
  originVerified: null,
  signatureValid: null,
};

function safeParse(bytes: Uint8Array): Record<string, unknown> | null {
  try {
    return parsePayload(bytes);
  } catch {
    return null;
  }
}

/** Read a payload via pdf.js — for PDFs pdf-lib can't load (empty-password encrypted). See file note. */
export const pdfjsDecryptRead: DecryptRead = async (pdfBytes, encrypted = false) => {
  try {
    const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
    const pdf = await pdfjs.getDocument({ data: pdfBytes.slice(), verbosity: 0 }).promise;
    try {
      const meta = await pdf.getMetadata();
      const expectedHash = meta.metadata?.get("omspec:payloadhash") ?? null;
      const attachments = await pdf.getAttachments();
      const bytes: Uint8Array | null = attachments?.["om.json"]?.content ?? null;
      if (bytes === null) {
        return {
          state: "absent",
          payload: null,
          payloadHash: expectedHash,
          verification: UNVERIFIED,
        };
      }
      const payload = safeParse(bytes);
      if (expectedHash === null) {
        return { state: "present", payload, payloadHash: null, verification: { ...UNVERIFIED } };
      }
      const { hashValid, computedHash } = verifyIntegrity(bytes, expectedHash);
      return {
        state: hashValid ? "present" : "hash-mismatch",
        payload,
        payloadHash: computedHash,
        verification: { hashValid, originVerified: null, signatureValid: null },
      };
    } finally {
      await pdf.destroy();
    }
  } catch {
    return {
      state: encrypted ? "encrypted" : "absent",
      payload: null,
      payloadHash: null,
      verification: UNVERIFIED,
    };
  }
};
