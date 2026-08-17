import { hmacSha256Hex } from "./crypto.js";

/**
 * §Y publish webhook — the SENDER side (consumer-mode "Publish"). Builds the signed envelope a
 * consumer POSTs to a broker-configured receiver. Deterministic: the clock (`now`) and ids are
 * injected by the caller. Zero inference.
 */

export interface Verification {
  hashValid: boolean | null;
  originVerified: boolean | null;
  signatureValid: boolean | null;
}

export interface Envelope {
  envelopeVersion: string;
  event: string;
  id: string;
  publishedAt: string;
  sourceUrl: string;
  specVersion: string;
  payloadHash: string;
  verification: Verification;
  payload: Record<string, unknown>;
}

const ENVELOPE_VERSION = "1";
const SPEC_VERSION = "0.1";

/** Assemble the §Y envelope ([OM-HOOK-002]). `publishedAt` is RFC 3339 UTC `Z` from `now`. */
export function buildEnvelope(a: {
  event: string;
  sourceUrl: string;
  payload: Record<string, unknown>;
  payloadHash: string;
  verification: Verification;
  now: Date;
  id: string;
}): Envelope {
  return {
    envelopeVersion: ENVELOPE_VERSION,
    event: a.event,
    id: a.id,
    publishedAt: a.now.toISOString(),
    sourceUrl: a.sourceUrl,
    specVersion: SPEC_VERSION,
    payloadHash: a.payloadHash,
    verification: a.verification,
    payload: a.payload,
  };
}

/**
 * The §Y headers for one delivery ([OM-HOOK-003/004/005]). Signs the EXACT `rawBody` the caller
 * will transmit (never re-serialize the envelope, [OM-HOOK-006]); `OpenOM-Event-Id` is stable
 * across retries (== envelope.id), `OpenOM-Delivery-Id` is unique per attempt.
 */
export function signHeaders(a: {
  secret: string;
  timestampUnix: number;
  rawBody: string;
  envelope: Envelope;
  deliveryId: string;
  attempt: number;
}): Record<string, string> {
  const v1 = hmacSha256Hex(a.secret, `${a.timestampUnix}.${a.rawBody}`);
  return {
    "Content-Type": "application/json",
    "OpenOM-Event": a.envelope.event,
    "OpenOM-Event-Id": a.envelope.id,
    "OpenOM-Delivery-Id": a.deliveryId,
    "OpenOM-Delivery-Attempt": String(a.attempt),
    "OpenOM-Envelope-Version": a.envelope.envelopeVersion,
    "OpenOM-Timestamp": String(a.timestampUnix),
    "OpenOM-Signature": `t=${a.timestampUnix},v1=${v1}`,
  };
}

const _PRIVATE_HOSTS = new Set(["localhost", "metadata.google.internal"]);

/**
 * Reject an unsafe webhook target ([OM-SEC-001], §Y [OM-HOOK-011]). In-browser bound: HTTPS-only +
 * host/IP-literal blocklist (no DNS resolve-then-pin is possible pre-fetch in an extension; that is
 * the hosted server's job, and §Y also puts SSRF duty on the receiver). Throws on unsafe.
 */
export function assertSafeWebhookTarget(url: string): void {
  const u = new URL(url);
  if (u.protocol !== "https:") throw new Error(`webhook target must be https, got ${u.protocol}`);
  const host = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (_PRIVATE_HOSTS.has(host) || host.endsWith(".local")) {
    throw new Error(`webhook target host not allowed: ${host}`);
  }
  if (_isBlockedIpLiteral(host)) {
    throw new Error(`webhook target resolves to a blocked range: ${host}`);
  }
}

function _isBlockedIpLiteral(host: string): boolean {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  if (m) {
    const [a, b] = [Number(m[1]), Number(m[2])];
    if (a === 10 || a === 127) return true; // 10/8, 127/8
    if (a === 192 && b === 168) return true; // 192.168/16
    if (a === 172 && b >= 16 && b <= 31) return true; // 172.16/12
    if (a === 169 && b === 254) return true; // 169.254/16 (incl. metadata)
    if (a === 100 && b >= 64 && b <= 127) return true; // 100.64/10 (CGNAT)
    return false;
  }
  if (host.includes(":")) {
    // IPv6 literal: loopback ::1 and ULA fc00::/7 (fc.. / fd..)
    if (host === "::1") return true;
    return /^f[cd][0-9a-f]{0,2}:/.test(host);
  }
  return false;
}
