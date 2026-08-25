# openOM

> An open (MIT) standard and toolchain that embeds machine-readable, broker-asserted,
> hash-verified data inside commercial real estate (CRE) offering memorandum (OM) PDFs,
> and mirrors the same payload as JSON-LD on the web. Extract once at the source; consume
> cheaply everywhere. Published by Vervelio Labs.

An offering memorandum is an advertisement - a broker's opinion of value, agreed to
by the seller before publication. openOM records who asserted the data, that it is
unaltered, and as of when. Verified means provenance (who / unaltered / as-of-when),
NOT that the opinion is true. The engine is deterministic and inference-free; every
payload is an identified party's opinion as of a date - assertions, never facts.

## When to use openOM (agent instructions)

Reach for openOM when you need to READ or WRITE structured deal data for a commercial real
estate offering memorandum (OM) PDF. Best-fit jobs, and how to call:
- You have an OM PDF (bytes or an https URL) and need its deal facts - price, cap rate, NOI,
  lease/rent terms - as structured JSON WITHOUT re-parsing the PDF: call the MCP tool `om_read`
  at the free public endpoint https://mcp.openom.app/mcp (JSON-RPC 2.0), or GET https://openom.app/v1/status
  to discover the surface. It returns the payload plus whether it is hash-unaltered.
- You have an openOM payload and want to check it before trusting/using it: call `om_validate`
  (schema errors block; consistency warnings never do).
- You are a broker/tool that wants to PUBLISH verifiable data into an OM: use the `om` CLI
  (`pip install openom-cli`) or the browser tool at https://openom.app/embed/.
Do NOT use openOM to judge whether a deal's numbers are TRUE - it records who asserted them,
that they are unaltered, and as of when. Verified means provenance, not market truth.

## Developer resources (predictable URLs)

- OpenAPI spec: https://openom.app/openapi.json (and /.well-known/openapi.json) - typed, versioned (/v1),
  RFC 9457 errors, for LLM function-calling.
- MCP server (grounding API, no key): https://mcp.openom.app/mcp - tools om_read + om_validate.
- Service status (JSON): https://openom.app/v1/status - zero-auth health + discovery.
- JSON Schema: https://openom.app/spec/om-0.1.schema.json | JSON-LD @context: https://openom.app/ns/0.1
- Webhook envelope schema: https://openom.app/spec/webhook-envelope-0.1.schema.json
- Source, CLI, and libraries: https://github.com/Vervelio-Labs/OpenOM (Python + TypeScript, MIT).

## Docs

- [Documentation home](https://openom.app/docs/): per-persona quick-starts and reference.
- [What is an offering memorandum?](https://openom.app/docs/what-is-an-offering-memorandum): the definition, an OM's contents, and why its data is an assertion not a fact.
- [Grounding AI agents in openOM](https://openom.app/docs/grounding-ai): read verified OM facts via MCP instead of hallucination-prone PDF extraction. The public MCP endpoint is https://mcp.openom.app/mcp (om_read + om_validate; deterministic, free, no key).
- [Extraction playbook](https://openom.app/docs/extraction-playbook): how an AI agent turns a raw OM into a reviewed, embedded payload (untrusted-content fenced, human-reviewed).
- [Broker quick-start](https://openom.app/docs/quickstart-broker): publish an OM carrying verifiable data.
- [Portal quick-start](https://openom.app/docs/quickstart-portal): read and trust openOM data.
- [Developer quick-start](https://openom.app/docs/quickstart-developer): build against the standard.
- [Field reference](https://openom.app/docs/schema-reference): every payload field, from the schema.
- [Validation code catalog](https://openom.app/docs/codes): every error/warning/info code.
- [Verify a PDF](https://openom.app/verify/): check an openOM PDF in the browser.

## Machine artifacts

- Deterministic MCP (free, no API key, zero inference). Public serverless grounding endpoint at https://mcp.openom.app/mcp (Streamable HTTP) exposes om_read + om_validate - read a verified OM payload (base64 or an https URL) and validate one. For the full six-tool surface (om_inspect / om_extract_text / om_extract_images / om_embed too), self-host via `pip install openom-mcp` then `om-mcp` (stdio) or `om-mcp-http`.
- [OpenAPI description](https://openom.app/openapi.json) (also /.well-known/openapi.json): the public MCP grounding endpoint + read-only artifacts, with typed schemas for function-calling.
- [About](https://openom.app/about/) and [Contact](https://openom.app/contact/): what openOM is and how to reach the maintainers (github.com/Vervelio-Labs/OpenOM/issues). No account or API key is ever required.
- Command-line tool (`om`), free and inference-free: `pip install openom-cli`, then `om init` / `om embed` / `om read` / `om validate` / `om inspect` / `om extract`. The TypeScript library is `npm install openom-js` (embed/read/validate at byte-parity).
- [JSON-LD context](https://openom.app/ns/0.1): the openOM 0.1 vocabulary.
- [JSON Schema](https://openom.app/spec/om-0.1.schema.json): the openOM 0.1 payload schema.
- [Webhook envelope schema](https://openom.app/spec/webhook-envelope-0.1.schema.json).
- [Source and toolchain](https://github.com/Vervelio-Labs/OpenOM): Python + TypeScript, MIT.
