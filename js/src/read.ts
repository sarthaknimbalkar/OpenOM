import { verifyIntegrity } from "./verify.js";
import { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES } from "./parse.js";
import { OmIoError } from "./errors.js";

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
 * Read and verify an openOM payload from PDF bytes — the deterministic read
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
    // Prefer the bounded (pre-decompression) extractor on Node — parity with the Python core's
    // zlib-capped inflate (no memory spike on a flate bomb). Falls back to pdf.js elsewhere,
    // where the post-decompression size cap in parsePayload still applies.
    const bytes = (await boundedExtractOmJson(pdfBytes)) ?? (await readOmJsonBytes(pdf));

    if (bytes === null) {
      // No payload file. Nothing to surface, regardless of a dangling marker.
      return {
        state: "absent",
        payload: null,
        payloadHash: expectedHash,
        verification: UNVERIFIED,
      };
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

/**
 * Node-only bounded extraction of `om.json`: read the RAW (compressed) stream via pdf-lib and
 * inflate with a hard output ceiling, so a decompression bomb is rejected (OM-IO-BOMB) BEFORE it
 * is fully materialized — parity with the Python core (Task 5). Returns null (→ pdf.js fallback)
 * on any environment/shape it can't confidently handle; only throws OM-IO-BOMB on an over-cap
 * inflate. Browser consumers use the pdf.js path + the post-decompression cap in parsePayload.
 */
async function boundedExtractOmJson(
  pdfBytes: Uint8Array,
  maxBytes: number = DEFAULT_MAX_PAYLOAD_BYTES,
): Promise<Uint8Array | null> {
  let zlib: typeof import("node:zlib");
  try {
    zlib = await import("node:zlib");
  } catch {
    return null; // not Node — let pdf.js handle it
  }
  const { PDFDocument, PDFName, PDFArray, PDFDict, PDFRawStream, PDFString, PDFHexString } =
    await import("pdf-lib");
  let doc;
  try {
    doc = await PDFDocument.load(pdfBytes, { throwOnInvalidObject: false, updateMetadata: false });
  } catch {
    return null;
  }
  const af = doc.catalog.lookup(PDFName.of("AF")); // untyped: absent -> undefined, not a throw
  if (!(af instanceof PDFArray)) return null;
  for (let i = 0; i < af.size(); i++) {
    const filespec = doc.context.lookup(af.get(i));
    if (!(filespec instanceof PDFDict)) continue;
    const nameObj = filespec.lookup(PDFName.of("UF")) ?? filespec.lookup(PDFName.of("F"));
    const name =
      nameObj instanceof PDFString || nameObj instanceof PDFHexString ? nameObj.decodeText() : null;
    if (name !== "om.json") continue;
    const ef = filespec.lookup(PDFName.of("EF"));
    if (!(ef instanceof PDFDict)) return null;
    const streamRef = ef.get(PDFName.of("F")) ?? ef.get(PDFName.of("UF"));
    const stream = streamRef ? doc.context.lookup(streamRef) : undefined;
    if (!(stream instanceof PDFRawStream)) return null;
    const raw = Buffer.from(stream.contents);
    const filter = stream.dict.lookup(PDFName.of("Filter"));
    if (filter instanceof PDFName && filter.decodeText() === "FlateDecode") {
      try {
        return new Uint8Array(zlib.inflateSync(raw, { maxOutputLength: maxBytes }));
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code === "ERR_BUFFER_TOO_LARGE") {
          throw new OmIoError("OM-IO-BOMB", `embedded payload exceeds the ${maxBytes}-byte cap`);
        }
        return null; // corrupt/other filter chain — defer to pdf.js
      }
    }
    if (!filter) {
      if (raw.length > maxBytes) {
        throw new OmIoError("OM-IO-BOMB", `embedded payload exceeds the ${maxBytes}-byte cap`);
      }
      return new Uint8Array(raw);
    }
    return null; // unknown filter — defer to pdf.js
  }
  return null;
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
