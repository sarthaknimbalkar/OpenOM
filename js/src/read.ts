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
 * Read and verify an openOM payload from PDF bytes — the deterministic read orchestration seam
 * (§D.2.2 [OM-XMP-005]): detect (XMP `omspec:payloadHash`) → extract (`om.json` via `/AF` →
 * `/Filespec` → `/EF`) → decompress → recompute the §C hash and compare.
 *
 * Uses **pdf-lib** for structure (it parses object streams / compressed xref, [OM-XMP-006]) and a
 * runtime-agnostic inflate — Node's `zlib` (bounded, bomb-capped) or the platform `DecompressionStream`
 * (browser / MV3 service worker) — so the SAME reader runs in Node, the browser, and the extension
 * with **no pdf.js worker** dependency. The payload bytes are hashed EXACTLY as received
 * (`verifyIntegrity`), never re-canonicalized ([OM-CANON-008]); a hash mismatch still returns the
 * payload with `hashValid: false` ([OM-VAL-006]) — the caller MUST NOT trust it.
 */
export async function readPayloadFromBytes(pdfBytes: Uint8Array): Promise<ReadResult> {
  const pdfLib = await import("pdf-lib");
  let doc: import("pdf-lib").PDFDocument;
  try {
    doc = await pdfLib.PDFDocument.load(pdfBytes, {
      throwOnInvalidObject: false,
      updateMetadata: false,
    });
  } catch {
    // Encrypted or otherwise unparseable by pdf-lib (which can't decrypt streams). Fall back to
    // pdf.js, which decrypts empty-password PDFs. pdf.js needs a Worker, so in an MV3 service
    // worker `getDocument` throws → a graceful `absent` (encrypted OMs are an extension edge case).
    return readViaPdfjs(pdfBytes);
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

/**
 * Last-resort reader via pdf.js — only for PDFs pdf-lib cannot load (notably empty-password
 * encrypted files, which pdf.js decrypts). pdf.js requires a Worker; where none is available (an
 * MV3 service worker) `getDocument` throws and we return `absent`, never crash.
 */
async function readViaPdfjs(pdfBytes: Uint8Array): Promise<ReadResult> {
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
    return { state: "absent", payload: null, payloadHash: null, verification: UNVERIFIED };
  }
}

type PdfLib = typeof import("pdf-lib");

/** Read `omspec:payloadHash` from the catalog `/Metadata` XMP stream (case-insensitive element). */
async function readXmpPayloadHash(
  doc: import("pdf-lib").PDFDocument,
  { PDFName, PDFRawStream }: PdfLib,
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
  const m = /<omspec:payloadHash>\s*([^<\s]+)\s*<\/omspec:payloadHash>/i.exec(xml);
  return m?.[1] ?? null;
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
