# openOM public MCP — Cloudflare Worker (`/mcp-worker`)

The **public, serverless, read-only** openOM MCP server at `https://mcp.openom.app/mcp`.
Deterministic, zero inference (cardinal rule). Backed by the byte-parity [`openom-js`](../js) core so
it needs no Python/PyMuPDF — it runs on the edge, not a home box.

## Tools (MCP Streamable HTTP)
- **`om_read`** — read the embedded openOM payload from an OM PDF (input: `pdfBase64`, or an https
  `url` the Worker fetches — size-capped, https-only, internal/metadata hosts refused; it **follows up
  to 3 redirects**, re-checking the SSRF guard on each hop, so presigned S3/GCS + CDN links work).
  Returns the payload as an *assertion* + `verification` (incl. `originVerified` when the payload
  declares a same-domain `meta.canonicalUrl` mirror the Worker verifies), a `stale`/`diverged` flag
  when the mirror disagrees, and `payloadHash` (a dedupe key). Never verified market truth.
- **`om_validate`** — schema errors (block) + consistency warnings, via the eval-free ajv standalone
  validator (Workers forbid `new Function`, like the MV3 CSP).

**Batch:** send a JSON-RPC **array** (up to 20 requests per call) to read a back-catalog in one HTTP
round-trip; the response is an array (notifications omitted). Upstream OM bytes are edge-cached (~5 min).

**Rate limit:** ~120 requests / 60s per client IP (CF native Rate Limiting binding); over the limit
returns HTTP **429** with a `Retry-After` header — self-pace against it for a bulk ingest.

**Error codes** — tool failures return `isError: true` with a stable `code` so a batch consumer can
branch without matching prose:
| code | meaning | typical action |
|------|---------|----------------|
| `OM-IO-SSRF` | non-https / internal / metadata target (incl. via a redirect) | drop |
| `OM-IO-REDIRECT` | redirect refused / limit exceeded / missing `Location` | retry with own bytes |
| `OM-IO-FETCH` | upstream returned a non-2xx | retry / drop |
| `OM-IO-BOMB` | PDF exceeds the 25 MB cap | skip |
| `OM-IO-ARGS` | neither `pdfBase64` nor `url` supplied | fix the call |
| `OM-IO-UNKNOWN` | unexpected error | alert |

The heavier / author tools (`om_inspect` doc-classification, `om_extract_text`, `om_extract_images`,
`om_embed`) need PyMuPDF/pdf.js and stay in the Python server — self-host via `om-mcp` / `om-mcp-http`.

## Deploy
`npm install && npm run deploy` (wrangler). The build step regenerates the eval-free validator from
`spec/om-0.1.schema.json`. `mcp.openom.app` is attached as a Workers custom domain.
