# openOM

[![checks](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/pr.yml/badge.svg)](https://github.com/sarthaknimbalkar/OpenOM/actions/workflows/pr.yml)
[![toolchain: MIT](https://img.shields.io/badge/toolchain-MIT-green.svg)](LICENSE)
[![spec: CC-BY-4.0](https://img.shields.io/badge/spec-CC--BY--4.0-blue.svg)](spec/LICENSE)
[![spec version: 0.1](https://img.shields.io/badge/spec-0.1-informational.svg)](spec/)

> An open standard + toolchain that embeds a machine-readable, broker-asserted data payload
> inside commercial-real-estate offering-memorandum (OM) PDFs, and exposes the same payload as
> JSON-LD on the web. **Extract once at the source; consume infinitely, cheaply, downstream.**

Published by **[Vervelio Labs](https://verveliolabs.com)** (neutral steward). Dual-licensed: the
toolchain is MIT, the specification is CC-BY-4.0 (see [License](#license)).
Docs, the verifier, and the namespace live at **[openom.app](https://openom.app)**.

---

## Which of these are you?

Pick the door that matches your job. Each one is the shortest path to a working result.

| You are… | openOM gives you… | Start here | No install? |
|----------|-------------------|------------|-------------|
| **🏢 Broker** - I have an OM PDF and want to add verified deal data | A review form that embeds your deal into the PDF. **You never touch a terminal.** | **[openom.app/embed/](https://openom.app/embed/)** (in your browser) or the **[Chrome extension](https://chromewebstore.google.com/detail/openom/koconccgjacmafhabbiakodicffnaplb)** | ✅ Nothing to install; bytes never leave your machine |
| **🔌 Portal** - I run a listings site and want trust badges + payloads at scale | A drop-in `<openom-badge>` web component and a free read API | [Portal quickstart](https://openom.app/docs/quickstart-portal) → [`js/widget/`](js/widget/) + [`mcp.openom.app`](https://mcp.openom.app/mcp) | Badge is one `<script>` tag; read API needs no key |
| **💻 Developer** - I want to call the API in my own code | Clean Python + TypeScript libraries (embed / read / validate) | [Developer quickstart](#developer-quickstart) → [`examples/`](examples/) | `pip install openom-core` · `npm install openom-js` |
| **🤖 AI-builder** - I want to ground an agent on OM data | A free, deterministic, public MCP endpoint | [`mcp.openom.app/mcp`](https://mcp.openom.app/mcp) → [config](examples/mcp-config.json) | No key, no per-call cost |

---

## 🏢 Broker - you never need the terminal

**You have an OM PDF. You want to embed your deal data so machines can read it. That's it.**

**→ Go to [openom.app/embed/](https://openom.app/embed/).** No install, no account, no command
line. Your PDF never leaves your computer. You'll get a review form where you enter (or confirm)
the deal facts, then download an openOM version of your PDF. New to this? The
**[step-by-step broker guide](GETTING_STARTED.md)** walks the whole thing in plain language.

Prefer a browser extension you can reuse on any listing? Install
**[openOM from the Chrome Web Store](https://chromewebstore.google.com/detail/openom/koconccgjacmafhabbiakodicffnaplb)**
and use **author mode** - it remembers your name, brokerage, and license so you never retype them.

A few things that trip up first-time brokers:

- **Cap rate is a decimal.** A 6.25% cap rate is entered as `0.0625`, not `6.25`. The form tells
  you this; if you see a "greater than the maximum of 1" error, that's the fix.
- **On-device AI is optional.** The extension can pre-fill the form using Chrome's built-in AI, but
  it's a convenience, not a requirement - **entering the fields by hand is the normal, fully
  supported path.** If your Chrome doesn't have the model, just fill the form yourself.
- **Verified means provenance, not truth.** openOM records *who* asserted the deal, that it is
  *unaltered*, and *as of when* - it never claims your numbers are correct. See
  [Assertions, not facts](#assertions-not-facts).

You do **not** need the Python `om` CLI. It exists for developers and automated pipelines.

---

## 🔌 Portal - badges and payloads at scale

**You run a listings site. You want a trust badge next to each listing and to read openOM payloads
programmatically.** Full walkthrough: **[openom.app/docs/quickstart-portal](https://openom.app/docs/quickstart-portal)**.

Three ways in:

- **Drop-in badge (client-side).** The [`<openom-badge>`](js/widget/) web component renders the
  trust state next to a listing with one script tag. See [`examples/badge.html`](examples/badge.html).
- **Precompute the state (server-side, best for results grids).** Call `om_read` on the public MCP
  endpoint, then set the badge state from the response. Map it explicitly - `om_read` returns
  `state: "present"`, so derive the badge state:
  `state = (r.state === "present" && r.verification.hashValid) ? "integrity-ok" : (r.state === "hash-mismatch" ? "hash-mismatch" : "absent")`.
- **In your own code (Node).** `npm install openom-js` and import the reader
  (`readPayloadFromBytes`, `summarizeDeal`).

Note: **origin-verified** (✓✓) requires the mirror JSON and the PDF to share the same registrable
domain (§10.1). PDFs served from a separate CDN domain show **integrity-ok** (unaltered since
embed) but not origin-verified - host the mirror on the listing's own domain to reach ✓✓.

---

## 💻 Developer quickstart

```bash
pip install openom-core openom-cli   # the Python library + the `om` CLI
```

```bash
git clone https://github.com/sarthaknimbalkar/OpenOM
python OpenOM/examples/quickstart.py  # embed → read → validate, end to end
```

Python API (`from openom_core import embed, read, validate`) and the `om` CLI:

```bash
om init deal.json                    # scaffold a ready-to-edit payload (so "no deal.json" can't happen)
om profile set --broker "Jane Broker" --brokerage "Acme" --license "MI 6501-000000"  # once; auto-filled

om inspect  path/to/offering.pdf
om embed    path/to/offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16
om read     out.pdf
om validate deal.json                # schema 0.1 is bundled; --schema only to override it
```

The CLI coaches you as you go: `om` with no arguments routes non-developers to the browser, every
error names the next action, and `om init`/`om profile` remove the two things brokers trip on.

TypeScript:

```bash
npm install openom-js
```

```ts
import { embedPayload, readPayloadFromBytes, validatePayload } from "openom-js";
```

More runnable examples - including a browser badge and an MCP config - are in
[`examples/`](examples/).

---

## 🤖 AI-builder - ground an agent

**Point any MCP client at the free public endpoint and ask it to read an OM.**

```
https://mcp.openom.app/mcp
```

No API key, no per-call cost. It exposes two deterministic, read-only tools - `om_read` (from PDF
bytes or an https URL) and `om_validate`. Try it on the
[sample OM](https://openom.app/sample/openom-sample.pdf). Full grounding guide:
**[openom.app/docs/grounding-ai](https://openom.app/docs/grounding-ai)**.

Client config - see [`examples/mcp-config.json`](examples/mcp-config.json):

```json
{ "mcpServers": { "openom": { "url": "https://mcp.openom.app/mcp" } } }
```

Client only supports **stdio** (e.g. a Claude Desktop JSON config)? Use the mcp-remote bridge
instead:

```json
{ "mcpServers": { "openom": { "command": "npx", "args": ["-y", "mcp-remote", "https://mcp.openom.app/mcp"] } } }
```

Want the **full six-tool surface** (`om_inspect · om_extract_text · om_extract_images · om_read ·
om_validate · om_embed`)? Self-host it: `pip install openom-mcp`, then run `om-mcp` (stdio) or
`om-mcp-http` (HTTP).

---

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

## Browser extension

The MV3 Chrome extension detects/verifies openOM data on any PDF (**consumer mode**) and lets a
broker embed data into an OM without the CLI (**author mode**). Chrome **116+**; the same build
loads in **Edge**, and **Firefox** is roadmapped (see
[extension/README](extension/README.md#browser-support-145)).

**→ Install from the Chrome Web Store:**
**[openOM](https://chromewebstore.google.com/detail/openom/koconccgjacmafhabbiakodicffnaplb)**
(one click, auto-updates). **Not a developer and just want to embed one OM?** You don't even need the
extension - do it in your browser at [openom.app/embed/](https://openom.app/embed/).

**For developers**, to build and load it unpacked from a clone:

```bash
npm --prefix js install && npm --prefix extension install
npm --prefix extension run build      # → extension/dist (load this unpacked)
npm --prefix extension run package    # → extension/openom-extension-<version>.zip (Web Store upload)
```

Then open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select
`extension/dist`. Consumer mode is the toolbar popup; author mode opens from the popup's **"Embed a
payload…"** button (a side panel).

## No-browser distribution

- **CI / server-side:** the [openom-embed GitHub Action](.github/actions/openom-embed/) embeds or
  validates payloads in a broker's pipeline, and the `om` CLI does the same locally - no browser, no
  inference.
- **Verify without installing anything:** the hosted, fully client-side tool at
  <https://openom.app/verify/> reads a PDF in your browser and shows its openOM state (bytes never
  leave your machine).
- **Portals:** the embeddable [`<openom-badge>`](js/widget/) shows the trust badge next to a listing
  with one script tag.

## Repository layout

| Path | What |
|------|------|
| [`core/`](core/) | Python library - deterministic PDF/data verbs (embed, read, inspect, extract, validate). The heart of the standard. Zero inference deps. |
| [`cli/`](cli/) | The `om` command over `core`. |
| [`spec/`](spec/) | JSON Schema, sample payloads, `@context`/vocabulary, and the conformance **vectors** (JCS oracles + golden PDFs). **The product.** |
| [`mcp/`](mcp/) | Deterministic MCP server - the 6-tool surface (`om_inspect · om_extract_text · om_extract_images · om_read · om_validate · om_embed`) over `core`. Self-host stdio/HTTP (`om-mcp`/`om-mcp-http`); a free public read-only grounding endpoint (`om_read`+`om_validate`) runs on a Cloudflare Worker at [mcp.openom.app](https://mcp.openom.app/mcp) ([`mcp-worker/`](mcp-worker/)). |
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow, [GOVERNANCE.md](GOVERNANCE.md) for how the
standard evolves (RFCs, versioning, stability guarantees), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md) for the threat model. Full documentation lives at
<https://openom.app/docs/>.

## Status

**Pre-1.0, active development - the full toolchain is shipped and green.** Implemented: `core`
(embed/read/inspect/extract/validate), `cli` (`om`), `mcp` (six deterministic tools, self-host stdio/HTTP;
public read-only Worker at mcp.openom.app), `js` (`openom-js`, byte-parity with `core`), `spec` (schema 0.1, vectors,
`@context`, webhook envelope, codes registry), `process` (extraction playbook), and the two-persona
`extension` (consumer + author). Non-destructive embedding is proven across ~60 real producers; the
cross-implementation, JCS-differential-fuzz, and RFC 8785 anti-fork gates run in CI. The schema is
`0.1` and may change until 1.0.

## License

Dual-licensed. The **toolchain** (`core`, `cli`, `mcp`, `js`, `extension`) is [MIT](LICENSE); the
**specification** artifacts under [`spec/`](spec/) and the spec documents are
[CC-BY-4.0](spec/LICENSE). © 2026 Vervelio Labs.
