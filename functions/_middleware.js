// Cloudflare Pages Function: canonical-domain redirect (www -> apex, 301).
//
// Lives at the REPO ROOT (not in site/) on purpose: the deploy runs `wrangler pages deploy site`
// from the repo root, and wrangler compiles a `functions/` directory found at the invocation dir
// (a functions/ inside the deployed site/ dir is NOT picked up). This middleware runs on every
// request; www.openom.app/<path> 301s to openom.app/<path> (query preserved), and every non-www
// request passes straight through to the static asset via context.next(), so the apex, _headers
// (JSON-LD CORS + content-types), and _redirects are all unaffected.
//
// Pages `_redirects` matches on PATH only - it serves www as a 200 mirror - so a host->host
// canonical redirect must run here. See DEPLOY.md. Keep the host in sync with gen_site.py BASE.
export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname === "www.openom.app") {
    url.hostname = "openom.app";
    return Response.redirect(url.toString(), 301);
  }
  return context.next();
}
