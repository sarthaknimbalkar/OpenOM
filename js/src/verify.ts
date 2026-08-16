import { sha256Hex } from "./crypto.js";

/** Result of an integrity check ([OM-VAL-006]). */
export interface IntegrityResult {
  /** True iff the recomputed hash equals the expected `omspec:payloadHash`. */
  readonly hashValid: boolean;
  /** The recomputed `sha256:<lowercase-hex>` over the received bytes. */
  readonly computedHash: string;
}

/**
 * Compute the integrity hash of already-serialized payload bytes.
 *
 * Spec: §C [OM-CANON-003], [OM-CANON-008]. This is the CONSUMER path: it hashes
 * the received decompressed `om.json` bytes EXACTLY as received — no parse, no
 * NFC, no re-canonicalization. A conformant Producer stores exactly the JCS
 * preimage bytes ([OM-CANON-005]; `meta.signature` is forbidden in 0.1), so a
 * direct byte hash both answers "unaltered since embed?" and honours the
 * "MUST NOT silently re-normalize a received payload" rule ([OM-CANON-008]).
 * Contrast `payloadHash` (hash.ts), the PRODUCER path that canonicalizes.
 */
export function integrityHashOfBytes(payload: Uint8Array | string): string {
  const bytes = typeof payload === "string" ? new TextEncoder().encode(payload) : payload;
  return `sha256:${sha256Hex(bytes)}`;
}

/**
 * Verify received payload bytes against an expected `omspec:payloadHash`
 * ([OM-VAL-006]). On mismatch the caller MUST NOT present the payload as
 * trusted ([OM-XMP-003]).
 */
export function verifyIntegrity(
  payload: Uint8Array | string,
  expectedHash: string,
): IntegrityResult {
  const computedHash = integrityHashOfBytes(payload);
  return { hashValid: computedHash === expectedHash, computedHash };
}
