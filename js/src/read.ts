import { verifyIntegrity } from "./verify.js";
import { parsePayload } from "./parse.js";

/** Detection outcome ([OM-XMP-005]); `ambiguous` is reserved for a later pass. */
export type ReadState = "absent" | "present" | "hash-mismatch";

export interface ReadVerification {
  /** True = unaltered since embed; false = mismatch; null = no reference hash to check. */
  readonly hashValid: boolean | null;
  /** §10 layer 3 — null until consumer mode has a domain to check ([OM-PROF-004]). */
  readonly originVerified: boolean | null;
  /** §10 layer 4 — null forever in 0.1 ([OM-TRUST-002]). */
  readonly signatureValid: boolean | null;
}

export interface ReadResult {
  readonly state: ReadState;
  readonly payload: Record<string, unknown> | null;
  readonly payloadHash: string | null;
  readonly verification: ReadVerification;
}

const UNVERIFIED: ReadVerification = {
  hashValid: null,
  originVerified: null,
  signatureValid: null,
};

/**
 * Read and verify an OpenOM payload from PDF bytes — the deterministic read
 * orchestration seam (§D.2.2 [OM-XMP-005]): detect (XMP `omspec:payloadHash`)
 * → extract (`om.json` via `/AF`→`/Filespec`→`/EF`) → decompress → recompute
 * the §C hash and compare. Parses via pdf.js, which handles compressed object
 * streams ([OM-XMP-006]) that a byte-scan would miss.
 *
 * The payload bytes are hashed EXACTLY as received (`verifyIntegrity`), never
 * re-canonicalized ([OM-CANON-008]). A hash mismatch still returns the payload
 * with `hashValid: false` ([OM-VAL-006]) — the caller MUST NOT trust it.
 */
export async function readPayloadFromBytes(pdfBytes: Uint8Array): Promise<ReadResult> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  // Copy: pdf.js may detach the underlying ArrayBuffer.
  const pdf = await pdfjs.getDocument({ data: pdfBytes.slice(), verbosity: 0 }).promise;
  try {
    const expectedHash = await readXmpPayloadHash(pdf);
    const bytes = await readOmJsonBytes(pdf);

    if (bytes === null) {
      // No payload file. Nothing to surface, regardless of a dangling marker.
      return { state: "absent", payload: null, payloadHash: expectedHash, verification: UNVERIFIED };
    }

    const payload = safeParse(bytes);

    if (expectedHash === null) {
      // Degraded producer: payload present, no reference hash ([OM-XMP-008]).
      // Surface it but never report hashValid: true.
      return {
        state: "present",
        payload,
        payloadHash: null,
        verification: { ...UNVERIFIED },
      };
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
}

/** Parse the payload, returning null if the bytes are not a valid payload. */
function safeParse(bytes: Uint8Array): Record<string, unknown> | null {
  try {
    return parsePayload(bytes);
  } catch {
    return null;
  }
}

/**
 * Read `omspec:payloadHash` from the catalog XMP. pdf.js lowercases XMP local
 * names, so the property is keyed `omspec:payloadhash` regardless of the
 * writer's casing — which makes this robust across pikepdf/pdf-lib producers.
 */
async function readXmpPayloadHash(pdf: {
  getMetadata(): Promise<{ metadata?: { get(k: string): string | null } | null }>;
}): Promise<string | null> {
  const { metadata } = await pdf.getMetadata();
  if (!metadata) return null;
  return metadata.get("omspec:payloadhash") ?? null;
}

/**
 * Extract the decompressed `om.json` bytes. pdf.js merges the `/AF` array and
 * the `/EmbeddedFiles` name tree and decompresses the stream for us; we match
 * the payload on its decoded filename ([OM-EMB-014]).
 */
async function readOmJsonBytes(pdf: {
  getAttachments(): Promise<Record<string, { filename: string; content: Uint8Array }> | null>;
}): Promise<Uint8Array | null> {
  const attachments = await pdf.getAttachments();
  if (!attachments) return null;
  const entry = attachments["om.json"];
  return entry ? entry.content : null;
}
