import { hmac } from "@noble/hashes/hmac";
import { sha256 } from "@noble/hashes/sha2";
import { bytesToHex, utf8ToBytes } from "@noble/hashes/utils";

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

/**
 * Lowercase-hex HMAC-SHA256 of a UTF-8 message under a UTF-8 key — the webhook
 * signature primitive (§Y [OM-HOOK-003]). Same @noble/hashes backing as
 * `sha256Hex`, so Node/browser/extension produce identical signatures.
 */
export function hmacSha256Hex(key: string, msg: string): string {
  return bytesToHex(hmac(sha256, utf8ToBytes(key), utf8ToBytes(msg)));
}
