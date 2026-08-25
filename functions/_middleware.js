// Cloudflare Pages Function (repo root - where `wrangler pages deploy site` compiles it).
//
// Edge behaviors for agent-readiness (Vercel is-agentic / Ora) + SEO, all preserving the existing
// static site and design:
//   1. Canonical domain: 301 www.openom.app/<path> -> openom.app/<path>.
//   2. Live JSON API under /v1/ with RFC 9457 (application/problem+json) errors:
//        GET /v1/status          -> a JSON health/discovery doc (zero-auth), matches /openapi.json
//        GET /v1/ns/0.1          -> the JSON-LD @context (served from the static asset)
//        GET /v1/spec/<file>     -> the schema artifacts (served from the static asset)
//        any other /v1/*         -> 404 problem+json
//   3. JSON error negotiation: an unknown path requested with `Accept: application/json` gets a
//      problem+json 404 instead of the HTML shell (agents can't parse HTML errors).
//   4. Markdown content-negotiation (acceptmarkdown.com): `Accept: text/markdown` -> the .md variant
//      (unknown paths -> /404.md), with `Vary: Accept`. HTML pages also carry `Vary: Accept`.
// Every other request passes through to the static asset via context.next().
const SPEC_VERSION = "0.1";

function problem(status, code, title, detail) {
  return new Response(
    JSON.stringify({
      type: `https://openom.app/docs/errors#${code}`,
      title,
      status,
      code,
      detail,
    }),
    { status, headers: { "Content-Type": "application/problem+json", "Vary": "Accept" } },
  );
}

export async function onRequest(context) {
  const { request, next, env } = context;
  const url = new URL(request.url);

  if (url.hostname === "www.openom.app") {
    url.hostname = "openom.app";
    return Response.redirect(url.toString(), 301);
  }

  const path = url.pathname;
  const accept = request.headers.get("Accept") || "";
  const wantsJson = /\bapplication\/json\b/i.test(accept);
  const wantsMarkdown = request.method === "GET" && /\btext\/markdown\b/i.test(accept);

  // --- 2. Live JSON API under /v1/ ---
  if (path === "/v1/status" || path === "/v1/status/") {
    if (request.method !== "GET") return problem(405, "method_not_allowed", "Method not allowed", "Use GET.");
    return new Response(
      JSON.stringify({
        status: "ok",
        service: "openom",
        specVersion: SPEC_VERSION,
        mcpEndpoint: "https://mcp.openom.app/mcp",
        openapi: "https://openom.app/openapi.json",
        auth: "none",
        docs: "https://openom.app/docs/",
      }),
      { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=300" } },
    );
  }
  if (path.startsWith("/v1/")) {
    // Serve the versioned aliases from the static assets (e.g. /v1/ns/0.1 -> /ns/0.1).
    const assetPath = path.slice(3); // strip "/v1"
    const assetUrl = new URL(url);
    assetUrl.pathname = assetPath;
    const res = await env.ASSETS.fetch(new Request(assetUrl.toString(), { headers: request.headers }));
    if (res.ok) return res;
    return problem(404, "not_found", "Not found", `No resource at ${path}. See /openapi.json.`);
  }

  // --- 4. Markdown content-negotiation (serve a real .md variant if one exists) ---
  if (wantsMarkdown) {
    const mdPath = path === "/" ? "/index.md" : path.endsWith(".md") ? path : path.replace(/\/$/, "") + ".md";
    const md = await env.ASSETS.fetch(new Request(new URL(mdPath, url).toString()));
    if (md.status === 200) {
      const text = await md.text();
      if (!text.trimStart().startsWith("<")) {
        // real markdown (not the HTML 404 shell that Pages returns for a missing asset)
        return new Response(text, {
          status: 200,
          headers: { "Content-Type": "text/markdown; charset=utf-8", "Vary": "Accept" },
        });
      }
    }
  }

  const response = await next();

  // --- 3. Typed error negotiation on a real 404: JSON or markdown, per Accept ---
  if (response.status === 404 && wantsJson) {
    return problem(404, "not_found", "Not found", `No resource at ${path}. See /openapi.json or /sitemap.xml.`);
  }
  if (response.status === 404 && wantsMarkdown) {
    const nf = await env.ASSETS.fetch(new Request(new URL("/404.md", url).toString()));
    return new Response(await nf.text(), {
      status: 404,
      headers: { "Content-Type": "text/markdown; charset=utf-8", "Vary": "Accept" },
    });
  }

  // Advertise that GET pages negotiate a markdown/json variant.
  if (request.method === "GET") {
    const h = new Headers(response.headers);
    h.append("Vary", "Accept");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: h });
  }
  return response;
}
