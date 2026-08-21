import { verifyIntegrity } from "./verify.js";
import { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES } from "./parse.js";
import { OmIoError } from "./errors.js";

/** Detection outcome ([OM-XMP-005]); `ambiguous` is reserved for a later pass. `encrypted` = the PDF
 * is encrypted and could not be decrypted here, so no payload could be read (distinct from `absent`). */
export type ReadState = "absent" | "present" | "hash-mismatch" | "encrypted";

export interface ReadVerification {
  /** True = unaltered since embed; false = mismatch; null = no reference hash to check. */
  readonly hashValid: boolean | null;
  /** §10 layer 3 - null until consumer mode has a domain to check ([OM-PROF-004]). */
  readonly originVerified: boolean | null;
  /** §10 layer 4 - null forever in 0.1 ([OM-TRUST-002]). */
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
 * Read and verify an openOM payload from PDF bytes - the deterministic read orchestration seam
 * (§D.2.2 [OM-XMP-005]): detect (XMP `omspec:payloadHash`) → extract (`om.json` via `/AF` →
 * `/Filespec` → `/EF`) → decompress → recompute the §C hash and compare.
 *
 * Uses **pdf-lib** for structure (it parses object streams / compressed xref, [OM-XMP-006]) and a
 * runtime-agnostic inflate - Node's `zlib` (bounded, bomb-capped) or the platform `DecompressionStream`
 * (browser / MV3 service worker) - so the SAME reader runs in Node, the browser, and the extension
 * with **no pdf.js worker** dependency. The payload bytes are hashed EXACTLY as received
 * (`verifyIntegrity`), never re-canonicalized ([OM-CANON-008]); a hash mismatch still returns the
 * payload with `hashValid: false` ([OM-VAL-006]) - the caller MUST NOT trust it.
 */
export async function readPayloadFromBytes(
  pdfBytes: Uint8Array,
  decrypt?: import("./read-decrypt.js").DecryptRead,
): Promise<ReadResult> {
  const pdfLib = await import("pdf-lib");
  let doc: import("pdf-lib").PDFDocument;
  try {
    doc = await pdfLib.PDFDocument.load(pdfBytes, {
      throwOnInvalidObject: false,
      updateMetadata: false,
    });
  } catch (e) {
    // Encrypted or otherwise unparseable by pdf-lib (which can't decrypt streams). Report the distinct
    // `encrypted` state (vs `absent`) so the UI can say "can't read (encrypted)" ([#72]). An OPT-IN
    // pdf.js decrypt fallback (Node tooling, empty-password PDFs) is used only when provided - it is
    // NOT bundled into the deterministic path, so the MV3 service worker carries no pdf.js ([#106]).
    const encrypted =
      e instanceof pdfLib.EncryptedPDFError || /encrypt/i.test(String((e as Error)?.message ?? ""));
    if (decrypt) return decrypt(pdfBytes, encrypted);
    return {
      state: encrypted ? "encrypted" : "absent",
      payload: null,
      payloadHash: null,
      verification: UNVERIFIED,
    };
  }

  const expectedHash = await readXmpPayloadHash(doc, pdfLib);
  const bytes = await extractOmJson(doc, pdfLib, DEFAULT_MAX_PAYLOAD_BYTES);

  if (bytes === null) {
    return { state: "absent", payload: null, payloadHash: expectedHash, verification: UNVERIFIED };
  }
  const payload = safeParse(bytes);
  if (expectedHash === null) {
    // Degraded producer: payload present, no reference hash ([OM-XMP-008]). Never report hashValid.
    return { state: "present", payload, payloadHash: null, verification: { ...UNVERIFIED } };
  }
  const { hashValid, computedHash } = verifyIntegrity(bytes, expectedHash);
  return {
    state: hashValid ? "present" : "hash-mismatch",
    payload,
    payloadHash: computedHash,
    verification: { hashValid, originVerified: null, signatureValid: null },
  };
}

type PdfLib = typeof import("pdf-lib");

/** Read one `omspec:<prop>` from the catalog `/Metadata` XMP stream (case-insensitive element). */
async function readXmpProp(
  doc: import("pdf-lib").PDFDocument,
  { PDFName, PDFRawStream }: PdfLib,
  prop: string,
): Promise<string | null> {
  const meta = doc.catalog.lookup(PDFName.of("Metadata"));
  if (!(meta instanceof PDFRawStream)) return null;
  const raw = new Uint8Array(meta.contents);
  const filter = meta.dict.lookup(PDFName.of("Filter"));
  const xmlBytes =
    filter instanceof PDFName && filter.decodeText() === "FlateDecode"
      ? await inflate(raw, DEFAULT_MAX_PAYLOAD_BYTES)
      : raw;
  const xml = new TextDecoder().decode(xmlBytes);
  const m = new RegExp(`<omspec:${prop}>\\s*([^<\\s]+)\\s*</omspec:${prop}>`, "i").exec(xml);
  return m?.[1] ?? null;
}

const readXmpPayloadHash = (doc: import("pdf-lib").PDFDocument, pdfLib: PdfLib) =>
  readXmpProp(doc, pdfLib, "payloadHash");

/**
 * Read one omspec marker property directly from PDF bytes (loads the PDF itself). Used by the embed
 * path to carry provenance forward (#5/#166). Returns null on an unreadable/encrypted PDF or a
 * missing property - never throws.
 */
export async function readMarkerProp(pdfBytes: Uint8Array, prop: string): Promise<string | null> {
  try {
    const pdfLib = await import("pdf-lib");
    const doc = await pdfLib.PDFDocument.load(pdfBytes, {
      throwOnInvalidObject: false,
      updateMetadata: false,
    });
    return await readXmpProp(doc, pdfLib, prop);
  } catch {
    return null;
  }
}

/**
 * Extract the decompressed `om.json` bytes via pdf-lib: `/AF` → `/Filespec` (match decoded filename
 * `om.json`, [OM-EMB-014]) → `/EF/F` stream → inflate with a hard output ceiling (bomb-capped).
 * Returns null when no `om.json` is present. Throws OM-IO-BOMB on an over-cap inflate ([OM-SEC-002]).
 */
async function extractOmJson(
  doc: import("pdf-lib").PDFDocument,
  pdfLib: PdfLib,
  maxBytes: number,
): Promise<Uint8Array | null> {
  const { PDFName, PDFArray, PDFDict, PDFRawStream, PDFString, PDFHexString } = pdfLib;
  const af = doc.catalog.lookup(PDFName.of("AF"));
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
    const raw = new Uint8Array(stream.contents);
    const filter = stream.dict.lookup(PDFName.of("Filter"));
    if (filter instanceof PDFName && filter.decodeText() === "FlateDecode") {
      return inflate(raw, maxBytes);
    }
    if (!filter) {
      if (raw.length > maxBytes) {
        throw new OmIoError("OM-IO-BOMB", `embedded payload exceeds the ${maxBytes}-byte cap`);
      }
      return raw;
    }
    return null; // unsupported filter chain
  }
  return null;
}

/** Bounded zlib inflate: Node `zlib` (fast, bomb-capped) or the platform `DecompressionStream`. */
async function inflate(raw: Uint8Array, maxBytes: number): Promise<Uint8Array> {
  let zlib: typeof import("node:zlib") | null = null;
  try {
    zlib = await import("node:zlib");
  } catch {
    zlib = null; // not Node → DecompressionStream
  }
  if (zlib) {
    try {
      return new Uint8Array(zlib.inflateSync(raw, { maxOutputLength: maxBytes }));
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ERR_BUFFER_TOO_LARGE") {
        throw new OmIoError("OM-IO-BOMB", `embedded payload exceeds the ${maxBytes}-byte cap`);
      }
      throw e;
    }
  }
  return inflateStream(raw, maxBytes);
}

/** Browser/MV3 inflate via `DecompressionStream("deflate")` (zlib-wrapped), with a byte ceiling. */
async function inflateStream(raw: Uint8Array, maxBytes: number): Promise<Uint8Array> {
  const ds = new DecompressionStream("deflate"); // PDF FlateDecode = zlib format
  const writer = ds.writable.getWriter();
  void writer.write(new Uint8Array(raw)); // fresh ArrayBuffer-backed view (BufferSource under DOM lib)
  void writer.close();
  const reader = ds.readable.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > maxBytes) {
      throw new OmIoError("OM-IO-BOMB", `embedded payload exceeds the ${maxBytes}-byte cap`);
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return out;
}

/** Parse the payload, returning null if the bytes are not a valid payload. */
function safeParse(bytes: Uint8Array): Record<string, unknown> | null {
  try {
    return parsePayload(bytes);
  } catch {
    return null;
  }
}
