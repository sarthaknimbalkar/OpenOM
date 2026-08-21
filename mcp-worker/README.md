# openOM public MCP — Cloudflare Worker (`/mcp-worker`)

The **public, serverless, read-only** openOM MCP server at `https://mcp.openom.app/mcp`.
Deterministic, zero inference (cardinal rule). Backed by the byte-parity [`openom-js`](../js) core so
it needs no Python/PyMuPDF — it runs on the edge, not a home box.

## Tools (MCP Streamable HTTP)
- **`om_read`** — read the embedded openOM payload from an OM PDF (input: `pdfBase64`, or an https
  `url` the Worker fetches — size-capped, https-only, no internal/redirect targets). Returns the
  payload as an *assertion* + `verification.hashValid`; never as verified market truth.
- **`om_validate`** — schema errors (block) + consistency warnings, via the eval-free ajv standalone
  validator (Workers forbid `new Function`, like the MV3 CSP).

The heavier / author tools (`om_inspect` doc-classification, `om_extract_text`, `om_extract_images`,
`om_embed`) need PyMuPDF/pdf.js and stay in the Python server — self-host via `om-mcp` / `om-mcp-http`.

## Deploy
`npm install && npm run deploy` (wrangler). The build step regenerates the eval-free validator from
`spec/om-0.1.schema.json`. `mcp.openom.app` is attached as a Workers custom domain.
