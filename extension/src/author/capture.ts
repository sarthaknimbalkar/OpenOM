// Author-mode capture: turn PDF bytes into a Capture, reading any prior payload so the review panel
// can offer the reprice flow. Deterministic; the byte source (re-fetch or file) is chosen by panel.ts.
// A prior payload counts as a reprice base ONLY when it reads back cleanly (state "present"); a
// tampered file (hash-mismatch) or a plain PDF (absent) starts a fresh assertion.
import { readPayloadFromBytes, decryptPdf, type ReadResult } from "openom-js";

/** Cheap sniff that bytes are a PDF (the `%PDF-` signature within the first bytes) ([#65]). */
export function looksLikePdf(bytes: Uint8Array): boolean {
  const head = bytes.subarray(0, 8);
  const sig = [0x25, 0x50, 0x44, 0x46, 0x2d]; // %PDF-
  for (let start = 0; start <= head.length - sig.length; start++) {
    if (sig.every((b, i) => head[start + i] === b)) return true;
  }
  return false;
}

export interface Capture {
  readonly bytes: Uint8Array;
  /** Non-null only for a cleanly-readable existing payload — the reprice base. */
  readonly prior: ReadResult | null;
  /**
   * True when the PDF DID carry a payload that failed its integrity check (hash-mismatch): it is not
   * a reprice base, and the panel MUST warn that embedding will start a fresh assertion, not chain
   * from it ([#87]). A plain PDF (absent) leaves this false — that is a normal fresh embed.
   */
  readonly priorUnverified: boolean;
  /**
   * True when the PDF is encrypted AND we could not decrypt it in-browser (RC4, a real user password,
   * or out of scope) — embedPayload can't load it, so authoring is refused ([#107]).
   */
  readonly encrypted: boolean;
  /**
   * True when the PDF was empty-password permission-encrypted AES and we decrypted it in-browser ([#4]):
   * `bytes` is now the decrypted copy the embed uses, so the embedded OM will be UNENCRYPTED. The panel
   * surfaces this; the read state reflects the decrypted document (absent / present / reprice).
   */
  readonly wasDecrypted: boolean;
}

export async function captureFromBytes(
  bytes: Uint8Array,
  read: (b: Uint8Array) => Promise<ReadResult> = readPayloadFromBytes,
  decrypt: (b: Uint8Array) => Promise<Uint8Array | null> = decryptPdf,
): Promise<Capture> {
  let r = await read(bytes);
  let wasDecrypted = false;
  // Empty-password AES ([#4]): decrypt in-browser, then author against the decrypted bytes. Only
  // out-of-scope encryption (decrypt → null) keeps the #107 refuse.
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
  };
}
