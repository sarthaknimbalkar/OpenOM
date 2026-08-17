// Author-mode capture: turn PDF bytes into a Capture, reading any prior payload so the review panel
// can offer the reprice flow. Deterministic; the byte source (re-fetch or file) is chosen by panel.ts.
// A prior payload counts as a reprice base ONLY when it reads back cleanly (state "present"); a
// tampered file (hash-mismatch) or a plain PDF (absent) starts a fresh assertion.
import { readPayloadFromBytes, type ReadResult } from "openom-js";

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
  /** True when the PDF is encrypted — embedPayload can't load it, so authoring is refused ([#107]). */
  readonly encrypted: boolean;
}

export async function captureFromBytes(
  bytes: Uint8Array,
  read: (b: Uint8Array) => Promise<ReadResult> = readPayloadFromBytes,
): Promise<Capture> {
  const r = await read(bytes);
  return {
    bytes,
    prior: r.state === "present" ? r : null,
    priorUnverified: r.state === "hash-mismatch",
    encrypted: r.state === "encrypted",
  };
}
