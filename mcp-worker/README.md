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

**Same shape as the self-hosted Python server** ([Ma9]): `om_read` returns `{state, payload,
payloadHash, specVersion, sourceDocHash, verification, ...}` and `om_validate` returns `{ok, errors,
warnings, info, canonical:{hash}, ...}` — a superset of the `openom-mcp` responses, so a client
written against either server works against the other (branch on `ok` / `canonical.hash`,
`specVersion` / `sourceDocHash`). The SSRF/fetch `code` strings below are Worker-specific; a unified
cross-server error-code registry is tracked with the spec's code catalog.

**Batch:** send a JSON-RPC **array** (up to 20 requests per call) to read a back-catalog in one HTTP
round-trip; the response is an array (notifications omitted). Upstream OM bytes are edge-cached (~5 min).

**Rate limit:** ~120 requests / 60s per client IP (CF native Rate Limiting binding); over the limit
returns HTTP **429** with a `Retry-After` header — self-pace against it for a bulk ingest.

**Error codes** — tool failures return `isError: true` with a stable `code`. These are the **same
canonical `OM-IO-*` codes the self-hosted Python server emits** and [`/spec/requirements.json`](https://openom.app/spec/requirements.json)
defines, so a batch consumer can branch without matching prose and one client works against either server:
| code | meaning | typical action |
|------|---------|----------------|
| `OM-IO-002` | SSRF: internal / metadata / loopback target (incl. via a redirect) | drop |
| `OM-IO-008` | non-https URL, or neither `pdfBase64` nor `url` supplied | fix the call |
| `OM-IO-009` | redirect refused / limit exceeded / missing `Location` | retry with own bytes |
| `OM-IO-001` | upstream returned a non-2xx | retry / drop |
| `OM-IO-005` | PDF exceeds the 25 MB cap (or not a PDF) | skip |
| `OM-IO-010` | malformed PDF / unexpected read failure | alert |

The heavier / author tools (`om_inspect` doc-classification, `om_extract_text`, `om_extract_images`,
`om_embed`) need PyMuPDF/pdf.js and stay in the Python server — self-host via `om-mcp` / `om-mcp-http`.

## Deploy
`npm install && npm run deploy` (wrangler). The build step regenerates the eval-free validator from
`spec/om-0.1.schema.json`. `mcp.openom.app` is attached as a Workers custom domain.
