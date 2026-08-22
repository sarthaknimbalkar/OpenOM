// Detection = RE-FETCH the viewed PDF's bytes over the network. It never reads the browser PDF
// viewer's DOM/internals (§4, [OM-DoD-006]); the byte source of truth is the URL, re-fetched.
import { assertSafeUrl } from "openom-js";

/** A detailed re-fetch outcome so callers can tell "too big" from "couldn't fetch" ([M6]). */
export type RefetchResult =
  | { ok: true; bytes: Uint8Array }
  | { ok: false; reason: "oversize" | "fetch" };

export async function refetchPdfResult(
  url: string,
  maxBytes = 25_000_000,
  fetchImpl: typeof fetch = fetch,
): Promise<RefetchResult> {
  try {
    // #122 SSRF guard: a link-badge href (attacker-controlled page content) reaches here via the
    // service worker, so refuse internal/loopback/metadata IP-literal targets before fetching.
    assertSafeUrl(url);
    const resp = await fetchImpl(url);
    if (!resp.ok) return { ok: false, reason: "fetch" };
    const declared = Number(resp.headers.get("content-length") ?? "0");
    if (declared && declared > maxBytes) return { ok: false, reason: "oversize" }; // cheap pre-check
    // Stream with a running ceiling so a lying/absent content-length can't buffer an unbounded body
    // into memory before the cap ([#67]); fall back to arrayBuffer where no stream is exposed.
    if (resp.body) {
      const capped = await readCapped(resp.body, maxBytes);
      return capped ? { ok: true, bytes: capped } : { ok: false, reason: "oversize" };
    }
    const body = new Uint8Array(await resp.arrayBuffer());
    return body.byteLength > maxBytes ? { ok: false, reason: "oversize" } : { ok: true, bytes: body };
  } catch {
    return { ok: false, reason: "fetch" };
  }
}

export async function refetchPdf(
  url: string,
  maxBytes = 25_000_000,
  fetchImpl: typeof fetch = fetch,
): Promise<Uint8Array | null> {
  const r = await refetchPdfResult(url, maxBytes, fetchImpl);
  return r.ok ? r.bytes : null;
}

/** Read a stream into bytes, aborting (and returning null) the moment it exceeds maxBytes. */
async function readCapped(
  stream: ReadableStream<Uint8Array>,
  maxBytes: number,
): Promise<Uint8Array | null> {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.byteLength;
  }
  return out;
}
