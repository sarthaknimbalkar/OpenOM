// The origin JSON-LD mirror fetch that feeds `verifyOrigin` (§10.1). MVP convention: a sibling
// `om.json` in the same directory as the source PDF. HTTPS-only + SSRF-host-guarded + size-capped.
import { assertSafeUrl } from "openom-js";

export function mirrorUrlFor(sourceUrl: string): string {
  const u = new URL(sourceUrl);
  const dir = u.pathname.replace(/[^/]*$/, ""); // strip the filename, keep the trailing slash
  return `${u.origin}${dir}om.json`;
}

export async function guardedMirrorFetch(
  mirrorUrl: string,
  maxBytes = 5_000_000,
  fetchImpl: typeof fetch = fetch,
): Promise<{ https: boolean; body: Uint8Array } | null> {
  try {
    assertSafeUrl(mirrorUrl); // #122/#125: https + SSRF host guard (throws → caught → null)
    const resp = await fetchImpl(mirrorUrl);
    if (!resp.ok) return null;
    const body = new Uint8Array(await resp.arrayBuffer());
    if (body.byteLength > maxBytes) return null;
    return { https: true, body };
  } catch {
    return null;
  }
}
