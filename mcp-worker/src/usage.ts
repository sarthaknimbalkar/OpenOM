// SPDX-License-Identifier: MIT
// Privacy-preserving aggregate usage for the public MCP endpoint (the adoption flywheel).
//
// The extension's "no tracking" promise is about the EXTENSION (which runs locally and sends
// nothing) - it is untouched. This instruments only the public Worker API, where aggregate
// request metrics are standard. We record, per tool call: the tool name, the result state, and a
// SALTED, HEAVILY-TRUNCATED hash of the OM host (16 bits). That hash is NOT the domain, is not
// reversible, and collides by design - so count(DISTINCT) estimates supply breadth (how many
// distinct OM-hosting domains are read) without storing any domain. Never recorded: client IP, the
// URL, the full domain, the payload, anything per-user. Best-effort via waitUntil; a metrics failure
// never affects the response.

/** Cloudflare Analytics Engine binding (wrangler.toml [[analytics_engine_datasets]]); absent in tests. */
export interface AnalyticsEngineDataset {
  writeDataPoint(point: { blobs?: string[]; doubles?: number[]; indexes?: string[] }): void;
}

/** Extract a lowercased hostname from a URL, or null if it isn't a parseable https URL (e.g. a
 *  pdfBase64 read has no host). */
export function hostOf(url: string | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

/** A salted 16-bit bucket for a host: SHA-256(salt + "\n" + host) truncated to 4 hex chars. Coarse
 *  enough (65 536 buckets, collision-heavy at scale) to be a breadth gauge, not a fingerprint; the
 *  salt keeps buckets from being a stable cross-dataset identifier. */
export async function hostBucket(host: string, salt: string): Promise<string> {
  const bytes = new TextEncoder().encode(`${salt}\n${host}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return (((digest[0] ?? 0) << 8) | (digest[1] ?? 0)).toString(16).padStart(4, "0");
}

/** Build the Analytics Engine data point for one tool call. blobs carry the dimensions; the host
 *  bucket is appended only when present. The tool name is also the sampling index. */
export function usagePoint(
  tool: string,
  state: string,
  bucket: string | null,
): { blobs: string[]; doubles: number[]; indexes: string[] } {
  const blobs = bucket ? [tool, state, bucket] : [tool, state];
  return { blobs, doubles: [1], indexes: [tool] };
}
