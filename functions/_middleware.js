// Cloudflare Pages Function (repo root - where `wrangler pages deploy site` compiles it).
//
// Two edge behaviors, both agent-readiness / SEO wins:
//   1. Canonical domain: 301 www.openom.app/<path> -> openom.app/<path> (path + query preserved).
//   2. Markdown content-negotiation (acceptmarkdown.com convention): when an agent sends
//      `Accept: text/markdown`, serve the .md representation of the page (e.g. `/` -> `/index.md`)
//      with `Vary: Accept`. HTML responses also carry `Vary: Accept` so the negotiation is
//      discoverable. Every non-www, non-markdown request passes straight through to the static
//      asset via context.next(), so the apex, _headers, and _redirects are unaffected.
//
// Keep the host in sync with gen_site.py BASE.
export async function onRequest(context) {
  const { request, next, env } = context;
  const url = new URL(request.url);

  if (url.hostname === "www.openom.app") {
    url.hostname = "openom.app";
    return Response.redirect(url.toString(), 301);
  }

  const accept = request.headers.get("Accept") || "";
  const wantsMarkdown = request.method === "GET" && /\btext\/markdown\b/i.test(accept);

  if (wantsMarkdown) {
    let mdPath = url.pathname;
    if (mdPath.endsWith("/")) mdPath += "index.md";
    else if (!mdPath.endsWith(".md")) mdPath += ".md";
    const mdUrl = new URL(url);
    mdUrl.pathname = mdPath;
    try {
      const res = await env.ASSETS.fetch(new Request(mdUrl.toString(), { headers: request.headers }));
      if (res.ok) {
        const h = new Headers(res.headers);
        h.set("Content-Type", "text/markdown; charset=utf-8");
        h.set("Vary", "Accept");
        return new Response(res.body, { status: 200, headers: h });
      }
    } catch {
      /* fall through to the HTML asset */
    }
  }

  const response = await next();
  if (request.method === "GET") {
    const h = new Headers(response.headers);
    h.append("Vary", "Accept"); // advertise that pages negotiate a markdown variant
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: h,
    });
  }
  return response;
}
