// Author-mode capture: turn PDF bytes into a Capture, reading any prior payload so the review panel
// can offer the reprice flow. Deterministic; the byte source (re-fetch or file) is chosen by panel.ts.
// A prior payload counts as a reprice base ONLY when it reads back cleanly (state "present"); a
// tampered file (hash-mismatch) or a plain PDF (absent) starts a fresh assertion.
import { readPayloadFromBytes, type ReadResult } from "openom-js";

export interface Capture {
  readonly bytes: Uint8Array;
  /** Non-null only for a cleanly-readable existing payload — the reprice base. */
  readonly prior: ReadResult | null;
}

export async function captureFromBytes(
  bytes: Uint8Array,
  read: (b: Uint8Array) => Promise<ReadResult> = readPayloadFromBytes,
): Promise<Capture> {
  const r = await read(bytes);
  return { bytes, prior: r.state === "present" ? r : null };
}
