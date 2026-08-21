import { payloadHash } from "./hash.js";
import type { Finding } from "./validate.js";

/**
 * Non-blocking re-embed warnings against an existing PDF (§H) - parity with the Python core's
 * `reembed_warnings`. Pure w.r.t. the PDF (reads the prior omspec marker via pdf.js); embedding
 * itself stays a separate step, so callers compose this to surface provenance issues.
 *
 * OMW-W051: the new assertedDate (taken from the payload, as the JS writer would embed it)
 * precedes the payload it would supersede - time going backwards on a reprice. Warnings never
 * block.
 */
export async function reembedWarnings(
  priorPdf: Uint8Array,
  payload: Record<string, unknown>,
): Promise<Finding[]> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  const pdf = await pdfjs.getDocument({ data: priorPdf.slice(), verbosity: 0 }).promise;
  try {
    const { metadata } = await pdf.getMetadata();
    if (!metadata) return [];
    const priorHash = metadata.get("omspec:payloadhash");
    const priorDate = metadata.get("omspec:asserteddate");
    if (!priorHash || !priorDate) return [];

    const newHash = payloadHash(payload);
    const newDate = String(payload["assertedDate"] ?? "");
    if (priorHash !== newHash && newDate && newDate < priorDate) {
      return [
        {
          code: "OMW-W051",
          severity: "warning",
          path: "/assertedDate",
          message: "assertedDate precedes the superseded payload's assertedDate",
          requirement: "OM-CONS-051",
          expected: priorDate,
          actual: newDate,
        },
      ];
    }
    return [];
  } finally {
    await pdf.destroy();
  }
}
