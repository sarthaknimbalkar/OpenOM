// Detection = RE-FETCH the viewed PDF's bytes over the network. It never reads the browser PDF
// viewer's DOM/internals (§4, [OM-DoD-006]); the byte source of truth is the URL, re-fetched.

export async function refetchPdf(
  url: string,
  maxBytes = 25_000_000,
  fetchImpl: typeof fetch = fetch,
): Promise<Uint8Array | null> {
  try {
    const resp = await fetchImpl(url);
    if (!resp.ok) return null;
    const declared = Number(resp.headers.get("content-length") ?? "0");
    if (declared && declared > maxBytes) return null; // cheap pre-check
    const body = new Uint8Array(await resp.arrayBuffer());
    if (body.byteLength > maxBytes) return null; // real cap
    return body;
  } catch {
    return null;
  }
}
