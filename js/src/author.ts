// Pure authoring helpers shared by the extension author mode AND the hosted authoring companion
// (js/widget). Turning a reviewed draft into the payload the broker asserts, choosing a download
// filename, and the assert-then-embed guard. Pure + clock-injected (the deterministic core never reads
// a clock): `today` is passed in. Zero inference. Single source so the two author surfaces can't diverge.
import type { ValidationReport } from "./validate.js";
import { readPayloadFromBytes, type ReadResult } from "./read.js";
import { decryptPdf } from "./decrypt.js";
import { pdfHasSignature } from "./signature.js";

/** Spec constants stamped at assertion - boilerplate, not broker-entered facts (§E). */
export const OM_CONTEXT: readonly string[] = ["https://schema.org", "https://openom.app/ns/0.1"];

export interface AssertedByProfile {
  broker: string;
  brokerage: string;
  license: string;
}

/**
 * Produce the payload the broker asserts: stamp the spec constants, `assertedBy` from the profile,
 * `assertedDate = today`; promote every rentSchedule `source` "extracted"→"asserted"; and on a reprice
 * set `meta.supersedes` to the prior payload's hash. Callers validate THIS shape (not the raw draft) so
 * the Assert gate reflects what would actually be embedded.
 */
export function finalizePayload(
  payload: Record<string, unknown>,
  profile: AssertedByProfile,
  today: string,
  prior: { payloadHash: string } | null,
  sourceDocHash?: string,
): Record<string, unknown> {
  const p = structuredClone(payload);
  p["@context"] = [...OM_CONTEXT];
  p["@type"] = "RealEstateListing";
  p["specVersion"] = "0.1";
  p["assertedBy"] = {
    broker: profile.broker,
    brokerage: profile.brokerage,
    license: profile.license,
  };
  p["assertedDate"] = today;

  const meta = (typeof p.meta === "object" && p.meta !== null ? p.meta : {}) as Record<
    string,
    unknown
  >;
  meta.supersedes = prior ? prior.payloadHash : (meta.supersedes ?? null);
  if (sourceDocHash) meta.sourceDocHash = sourceDocHash;
  p["meta"] = meta;

  const lease = p.lease as { rentSchedule?: Record<string, unknown>[] } | undefined;
  if (lease?.rentSchedule) {
    lease.rentSchedule = lease.rentSchedule.map((r) => ({
      ...r,
      source: r.source === "extracted" ? "asserted" : r.source,
    }));
  }
  return p;
}

/** Cheap sniff that bytes are a PDF (the `%PDF-` signature within the first bytes) ([#65]). */
export function looksLikePdf(bytes: Uint8Array): boolean {
  const head = bytes.subarray(0, 1024);
  const sig = [0x25, 0x50, 0x44, 0x46, 0x2d]; // %PDF-
  for (let start = 0; start <= head.length - sig.length; start++) {
    if (sig.every((b, i) => head[start + i] === b)) return true;
  }
  return false;
}

export interface Capture {
  readonly bytes: Uint8Array;
  /** Non-null only for a cleanly-readable existing payload - the reprice base. */
  readonly prior: ReadResult | null;
  /** True when the PDF carried a payload that FAILED its integrity check (hash-mismatch): not a
   * reprice base; the caller must warn that embedding starts a fresh assertion, not a chain ([#87]). */
  readonly priorUnverified: boolean;
  /** True when the PDF is encrypted AND could not be decrypted in-browser (RC4 / real password / out
   * of scope) - embedPayload can't load it, so authoring is refused ([#107]). */
  readonly encrypted: boolean;
  /** True when an empty-password permission-encrypted AES PDF was decrypted in-browser ([#4]): `bytes`
   * is the decrypted copy the embed uses, so the embedded OM will be UNENCRYPTED. */
  readonly wasDecrypted: boolean;
  /** True when the source PDF carries a digital signature / DocMDP certification ([M1]): embedding
   * rewrites the file and WILL invalidate that signature, so an author surface must warn first. */
  readonly signed: boolean;
}

/**
 * Turn PDF bytes into a Capture: read any prior payload (for the reprice base) and, for an
 * empty-password AES PDF, decrypt in-browser and author against the decrypted bytes ([#4]). Only
 * out-of-scope encryption (decrypt → null) keeps the #107 refuse. Pure; read/decrypt are injectable.
 */
export async function captureFromBytes(
  bytes: Uint8Array,
  read: (b: Uint8Array) => Promise<ReadResult> = readPayloadFromBytes,
  decrypt: (b: Uint8Array) => Promise<Uint8Array | null> = decryptPdf,
): Promise<Capture> {
  const signedSource = pdfHasSignature(bytes);
  let r = await read(bytes);
  let wasDecrypted = false;
  if (r.state === "encrypted") {
    const dec = await decrypt(bytes);
    if (dec !== null) {
      bytes = dec;
      r = await read(bytes);
      wasDecrypted = true;
    }
  }
  return {
    bytes,
    prior: r.state === "present" ? r : null,
    priorUnverified: r.state === "hash-mismatch",
    encrypted: r.state === "encrypted",
    wasDecrypted,
    // A decrypted copy is a fresh unsigned PDF; only an as-is source can carry a live signature.
    signed: !wasDecrypted && signedSource,
  };
}

/** Re-validate the final payload (must be error-free) then embed. Never embeds a schema-invalid OM. */
export async function assertAndEmbed(
  finalPayload: Record<string, unknown>,
  bytes: Uint8Array,
  validate: (p: Record<string, unknown>) => ValidationReport,
  embed: (b: Uint8Array, p: Record<string, unknown>) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  const report = validate(finalPayload);
  if (report.errors.length > 0) {
    throw new Error(
      `cannot embed: ${report.errors.length} schema error(s): ${report.errors.map((e) => e.code).join(", ")}`,
    );
  }
  return embed(bytes, finalPayload);
}

/**
 * A meaningful download name from the payload's street address (or the source URL's basename), always
 * ending `-openom.pdf`; falls back to `openom-embedded.pdf` ([#99]). Sanitized to a safe filename.
 */
export function suggestedFilename(payload: Record<string, unknown>, sourceUrl?: string): string {
  const addr = (payload.property as Record<string, unknown> | undefined)?.address as
    Record<string, unknown> | undefined;
  const street = typeof addr?.streetAddress === "string" ? addr.streetAddress : "";
  let base = street;
  if (!base && sourceUrl) {
    try {
      base =
        new URL(sourceUrl).pathname
          .split("/")
          .pop()
          ?.replace(/\.pdf$/i, "") ?? "";
    } catch {
      base = "";
    }
  }
  const slug = base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return slug ? `${slug}-openom.pdf` : "openom-embedded.pdf";
}
