# openOM

[![ci](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/ci.yml/badge.svg)](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/ci.yml)

> An open standard + toolchain that embeds a machine-readable, broker-asserted data payload
> inside commercial-real-estate offering-memorandum (OM) PDFs, and exposes the same payload as
> JSON-LD on the web. **Extract once at the source; consume infinitely, cheaply, downstream.**

Published by **[Vervelio Labs](https://verveliolabs.com)** (neutral steward). MIT-licensed.

## Why

Every downstream consumer of an OM — CRM, underwriting model, portal, LLM agent — re-extracts
the same facts from the same PDF, badly and repeatedly. openOM moves the extraction to the
**source**: the broker (or their tool) embeds a signed, versioned payload once, using the
[Factur-X](https://en.wikipedia.org/wiki/Factur-X) / PDF/A-3 attachment mechanism. The PDF
still looks byte-for-byte identical; a machine can now read the deal in milliseconds with zero
inference.

## The one rule that governs everything

**Deterministic core, inference at the edges.** The engine, MCP server, and consumer tooling
contain **zero LLM/inference calls, ever** — no keys, no per-call cost, fully testable. Any
LLM-assisted mapping runs client-side / on-device in the authoring layer only. This boundary is
enforced mechanically in CI (the `boundary` job fails if an inference/network client ever
enters the `core`/`cli`/`mcp` dependency tree).

## Assertions, not facts

Every payload is an identified party's **opinion as of a date** — `assertedBy` + `assertedDate`
are always required. Tooling checks *internal consistency* (NOI ÷ price vs cap rate, rent-schedule
math, date arithmetic) and **never** market truth. Schema errors block; consistency warnings
never do.

## Repository layout

| Path | What |
|------|------|
| [`core/`](core/) | Python library — deterministic PDF/data verbs (embed, read, inspect, extract, validate). The heart of the standard. Zero inference deps. |
| [`cli/`](cli/) | The `om` command over `core`. |
| [`spec/`](spec/) | JSON Schema, sample payloads, `@context`/vocabulary, and the conformance **vectors** (JCS oracles + golden PDFs). **The product.** |
| `mcp/` | Thin FastMCP wrapper (stdio + hosted HTTP). Deterministic. _(next milestone)_ |
| `js/` | TypeScript reference implementation (embed/read/validate) powering the extension + web/Node consumers. |
| `process/` | Extraction/mapping playbook for authoring clients. No code. _(planned)_ |
| `fixtures/` | Real OMs across producers (confidential; not committed). |

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

**Pre-1.0, active development.** The `core` engine + `cli` + `spec` contract (schema, vectors,
golden PDFs) are implemented and green; `mcp` and the browser extension are next. The schema is
`0.1` and may change until 1.0.

## License

[MIT](LICENSE) © 2026 Vervelio.
