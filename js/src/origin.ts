import { getDomain } from "tldts";
import { integrityHashOfBytes } from "./verify.js";

// PSL DEPENDENCY ([#80]): the same-registrable-domain check uses tldts, which bundles a SNAPSHOT of
// the Public Suffix List. As the PSL evolves (new eTLDs like *.github.io / country ccSLDs), a stale
// snapshot could mis-split a host. Keep tldts current: it is pinned in package.json and refreshed on
// the routine dependency-update cadence (Dependabot / manual bump), and the multi-label eTLD tests in
// origin.test.ts (co.uk, github.io) guard the behavior we depend on.

/**
 * Domain-origin verification - the §10.1 L3 check, consumer-mode. Proves "the entity controlling
 * this domain vouches for this exact payload": the source and its JSON-LD mirror are HTTPS, served
 * from the same registrable domain (eTLD+1), and the mirror's canonical hash equals the embedded
 * `omspec:payloadHash`. A rehost to another domain (A5) degrades gracefully to `origin-unverified`
 * - never an error ([OM-TRUST-005]). Deterministic; the mirror fetch is injected.
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
  // allowPrivateDomains: treat hosting-platform suffixes (github.io, *.herokuapp.com, …) as origin
  // boundaries, so one tenant's mirror can't vouch for another's payload ([#80]).
  const sourceDomain = getDomain(source.hostname, { allowPrivateDomains: true });
  const mirrorDomain = getDomain(mirror.hostname, { allowPrivateDomains: true });
  if (!sourceDomain || sourceDomain !== mirrorDomain) {
    return { originVerified: false, reason: "cross-origin" };
  }
  const fetched = await a.fetchMirror(a.mirrorUrl);
  if (!fetched || !fetched.https) {
    return { originVerified: false, reason: "unreachable" };
  }
  const mirrorHash = integrityHashOfBytes(fetched.body);
  if (!hashesEqual(mirrorHash, a.embeddedHash)) {
    return { originVerified: false, reason: "hash-mismatch", mirrorHash };
  }
  return { originVerified: true, reason: "ok", mirrorHash };
}

/**
 * Compare two `sha256:` digests up to formatting ([#81]): trim, lowercase, and tolerate a present /
 * absent `sha256:` prefix on either side. A valid-but-differently-cased or unprefixed embedded hash
 * must not read as a mismatch and silently drop origin verification. The digest itself must match.
 */
function hashesEqual(a: string, b: string): boolean {
  const norm = (h: string): string =>
    h
      .trim()
      .toLowerCase()
      .replace(/^sha256:/, "");
  return norm(a) === norm(b) && norm(a).length > 0;
}
