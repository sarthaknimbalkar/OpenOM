import { hmacSha256Hex, timingSafeEqualHex } from "./crypto.js";

/**
 * §Y publish webhook - the SENDER side (consumer-mode "Publish"). Builds the signed envelope a
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

export interface VerifyResult {
  valid: boolean;
  reason: "ok" | "malformed-header" | "bad-signature" | "stale";
}

/**
 * RECEIVER-side verification of a §Y delivery ([OM-HOOK-003], the two-sided half of the standard).
 * Recomputes HMAC over the EXACT `<t>.<rawBody>` preimage the sender signed (never re-serialize the
 * body), compares in constant time, and enforces a replay window: reject if `|now - t| > toleranceSec`.
 * `rawBody` MUST be the exact received bytes as text; `signatureHeader` is the `OpenOM-Signature` value.
 */
export function verifyWebhookSignature(a: {
  rawBody: string;
  signatureHeader: string;
  secret: string;
  nowUnix: number;
  toleranceSec?: number;
}): VerifyResult {
  const tolerance = a.toleranceSec ?? 300;
  const m = /^t=(\d+),v1=([0-9a-f]+)$/.exec(a.signatureHeader.trim());
  if (!m || m[1] === undefined || m[2] === undefined) {
    return { valid: false, reason: "malformed-header" };
  }
  const t = Number(m[1]);
  const provided = m[2];
  const expected = hmacSha256Hex(a.secret, `${t}.${a.rawBody}`);
  if (!timingSafeEqualHex(provided, expected)) return { valid: false, reason: "bad-signature" };
  if (Math.abs(a.nowUnix - t) > tolerance) return { valid: false, reason: "stale" };
  return { valid: true, reason: "ok" };
}

const _PRIVATE_HOSTS = new Set(["localhost", "metadata.google.internal"]);

/**
 * Reject an unsafe webhook target ([OM-SEC-001], §Y [OM-HOOK-011]). In-browser bound: HTTPS-only +
 * host/IP-literal blocklist (no DNS resolve-then-pin is possible pre-fetch in an extension; that is
 * the hosted server's job, and §Y also puts SSRF duty on the receiver). Throws on unsafe.
 *
 * The IP check NORMALIZES every literal encoding a browser/curl will still resolve - dotted-quad,
 * dword-decimal, octal, hex, short forms, and IPv4-mapped IPv6 - so `http://2130706433`,
 * `http://0x7f.1`, and `[::ffff:127.0.0.1]` are all rejected, not just `127.0.0.1` ([#79]).
 */
export function assertSafeWebhookTarget(url: string): void {
  assertSafeUrl(url, "webhook target");
}

/**
 * SSRF host guard for ANY outbound fetch ([#122]): https only, and the host must not be a private /
 * loopback / link-local / CGNAT / metadata IP literal (every inet_aton + IPv6 encoding). Reused by the
 * extension's PDF re-fetch and origin-mirror fetch so an attacker-supplied link-badge href cannot steer
 * the service worker at 169.254.169.254 or an internal host. Caveat (same as the webhook path): the
 * browser cannot resolve DNS, so a hostname that RESOLVES to a private IP is not caught here - the
 * hosted /mcp fetch.py resolve-then-pin guard covers that server-side.
 */
export function assertSafeUrl(url: string, label = "fetch target"): void {
  const u = new URL(url);
  if (u.protocol !== "https:") throw new Error(`${label} must be https, got ${u.protocol}`);
  const host = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  // Reserved/internal name spaces: bare `localhost`, and the .localhost/.internal/.local suffixes
  // (parity with the Worker's hostname guard), so `app.localhost` / `foo.internal` are refused too.
  if (
    _PRIVATE_HOSTS.has(host) ||
    host.endsWith(".localhost") ||
    host.endsWith(".internal") ||
    host.endsWith(".local")
  ) {
    throw new Error(`${label} host not allowed: ${host}`);
  }
  if (_isBlockedIp(host)) {
    throw new Error(`${label} resolves to a blocked range: ${host}`);
  }
}

/** True if the host is (any encoding of) a private / loopback / link-local / CGNAT / unspecified IP. */
function _isBlockedIp(host: string): boolean {
  if (host.includes(":")) return _isBlockedIpv6(host);
  const int = _ipv4ToInt(host);
  return int !== null && _isBlockedV4Int(int);
}

/** Range check on a 32-bit IPv4 integer. */
function _isBlockedV4Int(n: number): boolean {
  const a = (n >>> 24) & 0xff;
  const b = (n >>> 16) & 0xff;
  if (a === 0 || a === 10 || a === 127) return true; // 0/8 (unspecified), 10/8, 127/8
  if (a === 192 && b === 168) return true; // 192.168/16
  if (a === 172 && b >= 16 && b <= 31) return true; // 172.16/12
  if (a === 169 && b === 254) return true; // 169.254/16 (incl. cloud metadata)
  if (a === 100 && b >= 64 && b <= 127) return true; // 100.64/10 (CGNAT)
  if (a >= 224 && a <= 239) return true; // 224.0.0.0/4 multicast
  return false;
}

/**
 * Parse an IPv4 literal in any inet_aton encoding to a 32-bit int, or null if it is not one.
 * Accepts 1–4 dot-separated parts, each decimal / 0-octal / 0x-hex; a short form's final part fills
 * the remaining low bytes (e.g. `127.1` → 127.0.0.1, `2130706433` → 127.0.0.1).
 */
function _ipv4ToInt(host: string): number | null {
  const parts = host.split(".");
  if (parts.length < 1 || parts.length > 4) return null;
  const nums: number[] = [];
  for (const p of parts) {
    if (p === "") return null;
    let v: number;
    if (/^0x[0-9a-f]+$/.test(p)) v = parseInt(p.slice(2), 16);
    else if (/^0[0-7]*$/.test(p)) v = parseInt(p, 8);
    else if (/^[1-9]\d*$/.test(p)) v = parseInt(p, 10);
    else return null;
    if (!Number.isFinite(v)) return null;
    nums.push(v);
  }
  const last = nums.length - 1;
  const lastVal = nums[last];
  if (lastVal === undefined) return null;
  if (lastVal >= 2 ** (8 * (4 - last))) return null; // the final part may span the remaining bytes
  let int = lastVal;
  for (let i = 0; i < last; i++) {
    const v = nums[i];
    if (v === undefined || v > 0xff) return null;
    int += v * 2 ** (8 * (3 - i));
  }
  return int >>> 0;
}

/**
 * Block IPv6 loopback (::1), unspecified (::), ULA fc00::/7, link-local fe80::/10, and mapped v4 -
 * in EVERY textual form. Prior code string-matched "::1"/"::" only, so uncompressed/alternate forms
 * like 0:0:0:0:0:0:0:1 bypassed it ([#125]); we now expand to 8 groups and range-check numerically.
 */
function _isBlockedIpv6(host: string): boolean {
  const g = _expandIpv6(host);
  if (g === null) return false;
  if (g.slice(0, 5).every((x) => x === 0) && g[5] === 0xffff) {
    return _isBlockedV4Int((((g[6] ?? 0) << 16) | (g[7] ?? 0)) >>> 0); // ::ffff:v4 mapped
  }
  // NAT64 well-known prefix 64:ff9b::/96 embeds the target IPv4 in the last two groups.
  if (g[0] === 0x0064 && g[1] === 0xff9b && g.slice(2, 6).every((x) => x === 0)) {
    return _isBlockedV4Int((((g[6] ?? 0) << 16) | (g[7] ?? 0)) >>> 0);
  }
  if (g[0] === 0x2002) return true; // 6to4 (2002::/16, deprecated) - no legitimate public literal
  if (g.every((x) => x === 0)) return true; // :: unspecified
  if (g.slice(0, 7).every((x) => x === 0) && g[7] === 1) return true; // ::1 loopback (any form)
  const first = g[0] ?? 0;
  if ((first & 0xfe00) === 0xfc00) return true; // fc00::/7 ULA
  if ((first & 0xffc0) === 0xfe80) return true; // fe80::/10 link-local
  return false;
}

/** Expand an IPv6 literal (incl. `::` compression and a trailing embedded v4) to 8 groups, or null. */
function _expandIpv6(host: string): number[] | null {
  if (!/^[0-9a-f:.]+$/.test(host) || (host.match(/::/g) ?? []).length > 1) return null;
  let h = host;
  const v4 = /^(.*:)(\d+\.\d+\.\d+\.\d+)$/.exec(h);
  if (v4 && v4[1] !== undefined && v4[2] !== undefined) {
    const int = _ipv4ToInt(v4[2]);
    if (int === null) return null;
    h = `${v4[1]}${((int >>> 16) & 0xffff).toString(16)}:${(int & 0xffff).toString(16)}`;
  }
  const [headStr, tailStr] = h.split("::");
  const head = headStr ? headStr.split(":") : [];
  const hasCompression = h.includes("::");
  const tail = hasCompression ? (tailStr ? tailStr.split(":") : []) : null;
  let groups: string[];
  if (tail === null) {
    groups = head;
  } else {
    const fill = 8 - head.length - tail.length;
    if (fill < 0) return null;
    groups = [...head, ...Array<string>(fill).fill("0"), ...tail];
  }
  if (groups.length !== 8) return null;
  const out: number[] = [];
  for (const grp of groups) {
    if (!/^[0-9a-f]{1,4}$/.test(grp)) return null;
    out.push(parseInt(grp, 16));
  }
  return out;
}
