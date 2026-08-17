import { getDomain } from "tldts";
import { integrityHashOfBytes } from "./verify.js";

/**
 * Domain-origin verification — the §10.1 L3 check, consumer-mode. Proves "the entity controlling
 * this domain vouches for this exact payload": the source and its JSON-LD mirror are HTTPS, served
 * from the same registrable domain (eTLD+1), and the mirror's canonical hash equals the embedded
 * `omspec:payloadHash`. A rehost to another domain (A5) degrades gracefully to `origin-unverified`
 * — never an error ([OM-TRUST-005]). Deterministic; the mirror fetch is injected.
 */

export interface OriginResult {
  originVerified: boolean;
  reason: "ok" | "not-https" | "cross-origin" | "unreachable" | "hash-mismatch";
  mirrorHash?: string;
}

export type MirrorFetch = (url: string) => Promise<{ https: boolean; body: Uint8Array } | null>;

export async function verifyOrigin(a: {
  sourceUrl: string;
  mirrorUrl: string;
  embeddedHash: string;
  fetchMirror: MirrorFetch;
}): Promise<OriginResult> {
  const source = new URL(a.sourceUrl);
  const mirror = new URL(a.mirrorUrl);
  if (source.protocol !== "https:" || mirror.protocol !== "https:") {
    return { originVerified: false, reason: "not-https" };
  }
  if (getDomain(source.hostname) !== getDomain(mirror.hostname) || !getDomain(source.hostname)) {
    return { originVerified: false, reason: "cross-origin" };
  }
  const fetched = await a.fetchMirror(a.mirrorUrl);
  if (!fetched || !fetched.https) {
    return { originVerified: false, reason: "unreachable" };
  }
  const mirrorHash = integrityHashOfBytes(fetched.body);
  if (mirrorHash !== a.embeddedHash) {
    return { originVerified: false, reason: "hash-mismatch", mirrorHash };
  }
  return { originVerified: true, reason: "ok", mirrorHash };
}
