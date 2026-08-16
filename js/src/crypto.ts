import { sha256 } from "@noble/hashes/sha2";
import { bytesToHex } from "@noble/hashes/utils";

/**
 * Lowercase-hex SHA-256 of raw bytes.
 *
 * Uses @noble/hashes (audited, dependency-free, synchronous, isomorphic) so
 * `/js` produces byte-identical hashes in Node, the browser, and the extension
 * consumer — the one place a Web/Node split could silently fork the standard.
 * Spec: §C [OM-CANON-003] (lowercase hex).
 */
export function sha256Hex(bytes: Uint8Array): string {
  return bytesToHex(sha256(bytes));
}
