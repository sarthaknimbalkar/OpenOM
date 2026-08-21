# openOM

[![ci](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/ci.yml/badge.svg)](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/ci.yml)

> An open standard + toolchain that embeds a machine-readable, broker-asserted data payload
> inside commercial-real-estate offering-memorandum (OM) PDFs, and exposes the same payload as
> JSON-LD on the web. **Extract once at the source; consume infinitely, cheaply, downstream.**

Published by **[Vervelio Labs](https://verveliolabs.com)** (neutral steward). Dual-licensed: the
toolchain is MIT, the specification is CC-BY-4.0 (see [License](#license)).

## Why

Every downstream consumer of an OM - CRM, underwriting model, portal, LLM agent - re-extracts
the same facts from the same PDF, badly and repeatedly. openOM moves the extraction to the
**source**: the broker (or their tool) embeds a signed, versioned payload once, using the
[Factur-X](https://en.wikipedia.org/wiki/Factur-X) / PDF/A-3 attachment mechanism. The PDF
still looks byte-for-byte identical; a machine can now read the deal in milliseconds with zero
inference.

## The one rule that governs everything

**Deterministic core, inference at the edges.** The engine, MCP server, and consumer tooling
contain **zero LLM/inference calls, ever** - no keys, no per-call cost, fully testable. Any
LLM-assisted mapping runs client-side / on-device in the authoring layer only. This boundary is
enforced mechanically in CI (the `boundary` job fails if an inference/network client ever
enters the `core`/`cli`/`mcp` dependency tree).

## Assertions, not facts

An OM is an **advertisement** - a broker's **opinion of value**, which the seller agreed to before
it was published. So every payload is an identified party's **opinion as of a date** (`assertedBy` +
`assertedDate` are always required), and openOM records **who** asserted it, that it is
**unaltered**, and **as of when** - it never claims the opinion is *true*. **Verified means
provenance, not truth.** Tooling checks *internal consistency* (NOI ÷ price vs cap rate,
rent-schedule math, date arithmetic) and **never** market truth. Schema errors block; consistency
warnings never do.

## Repository layout

| Path | What |
|------|------|
| [`core/`](core/) | Python library - deterministic PDF/data verbs (embed, read, inspect, extract, validate). The heart of the standard. Zero inference deps. |
| [`cli/`](cli/) | The `om` command over `core`. |
| [`spec/`](spec/) | JSON Schema, sample payloads, `@context`/vocabulary, and the conformance **vectors** (JCS oracles + golden PDFs). **The product.** |
| [`mcp/`](mcp/) | Deterministic MCP server - the 6-tool surface (`om_inspect · om_extract_text · om_extract_images · om_read · om_validate · om_embed`) over `core`. stdio (M1); hosted HTTP is M3. |
| [`js/`](js/) | TypeScript reference implementation (`openom-js`) - embed/read/validate/verify/decrypt - powering the extension + web/Node consumers. Byte-parity with `core`. |
| [`extension/`](extension/) | MV3 Chrome extension: consumer mode (detect/verify/badge/publish) + author mode (capture/review/assert/embed, on-device extraction). |
| [`process/`](process/) | Extraction/mapping playbook (`SKILL.md` + agent-instructions) for authoring clients. No code. |
| `fixtures/` | Seeded-defect + producer-diverse fixtures (committed for CI); the full real-OM corpus is confidential (gitignored). |

**Cardinal boundary:** `core/`, `mcp/`, and consumer-mode `js/` never import an inference client.

## The cross-implementation guarantee

The Python (`core`) and TypeScript (`js`) implementations MUST produce **byte-identical**
canonical JSON ([RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785)) and therefore the same
SHA-256 integrity hash. This is the anti-fork oracle: [`spec/vectors/`](spec/vectors/) holds
payloads with their expected canonical bytes/hash plus golden embedded PDFs, and CI runs each
implementation against the other's output on every commit (`[OM-VEC-002]`).

## Quick start (Python)

```bash
pip install -e "core[dev]" -e "cli[dev]"

om inspect  path/to/offering.pdf
om embed    path/to/offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16
om read     out.pdf
om validate deal.json --schema spec/om-0.1.schema.json
```

## Browser extension (consumer + author)

The MV3 Chrome extension detects/verifies openOM data on any PDF and lets a broker embed data into an
OM without the CLI. Chrome **116+**.

```bash
npm --prefix js install && npm --prefix extension install
npm --prefix extension run build      # → extension/dist (load this unpacked)
npm --prefix extension run package    # → extension/openom-extension-<version>.zip (Web Store upload)
```

**Install (until it's on the Web Store):** open `chrome://extensions`, enable **Developer mode**, click
**Load unpacked**, and select `extension/dist`. The same build loads in **Edge** (`edge://extensions`);
**Firefox** is roadmapped (see [extension/README](extension/README.md#browser-support-145)). Consumer
mode is the toolbar popup; author mode opens from the popup's **“Embed a payload…”** button (a side panel).

## No-browser distribution

- **CI / server-side:** the [openom-embed GitHub Action](.github/actions/openom-embed/) embeds or
  validates payloads in a broker's pipeline, and the `om` CLI does the same locally - no browser, no
  inference.
- **Verify without installing anything:** the hosted, fully client-side tool at `…/openom/verify/`
  reads a PDF in your browser and shows its openOM state (bytes never leave your machine).
- **Portals:** the embeddable [`<openom-badge>`](js/widget/) shows the trust badge next to a listing
  with one script tag.

## Development

```bash
pip install -e "core[dev]" -e "cli[dev]"
pre-commit install                       # optional local guardrails

ruff check core/src core/tests core/scripts cli/src cli/tests
mypy core/src && mypy cli/src
pytest core -q --cov=openom_core --cov-fail-under=90
pytest cli  -q --cov=openom_cli  --cov-fail-under=90
python core/scripts/gen_vectors.py       # regenerate vectors (must be a no-op = no drift)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and [SECURITY.md](SECURITY.md) for
the threat model.

## Status

**Pre-1.0, active development - the full toolchain is shipped and green.** Implemented: `core`
(embed/read/inspect/extract/validate), `cli` (`om`), `mcp` (six deterministic tools, stdio +
hosted Streamable HTTP), `js` (`openom-js`, byte-parity with `core`), `spec` (schema 0.1, vectors,
`@context`, webhook envelope, codes registry), `process` (extraction playbook), and the two-persona
`extension` (consumer + author). Non-destructive embedding is proven across ~60 real producers; the
cross-implementation, JCS-differential-fuzz, and RFC 8785 anti-fork gates run in CI. The schema is
`0.1` and may change until 1.0.

## License

Dual-licensed. The **toolchain** (`core`, `cli`, `mcp`, `js`, `extension`) is [MIT](LICENSE); the
**specification** artifacts under [`spec/`](spec/) and the spec documents are
[CC-BY-4.0](spec/LICENSE). © 2026 Vervelio Labs.
