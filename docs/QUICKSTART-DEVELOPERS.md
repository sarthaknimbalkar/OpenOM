# openOM quickstart - Developer, Portal & AI-builder

Three integration paths, one deterministic core. Everything below is inference-free, needs no API
key, and has no per-call cost. Full docs live at **<https://openom.app/docs/>**; this file is the
in-repo copy for people reading the source.

> Not a developer? If you just have an OM PDF and want to embed deal data, you never touch a
> terminal - use the browser tool at **<https://openom.app/embed/>** (bytes never leave your
> machine). See [`docs/QUICKSTART-BROKER.md`](QUICKSTART-BROKER.md) if present, or the extension.

**Packaging note (read once):** `openom-core`, `openom-mcp`, and `openom-js` are **not yet published**
to PyPI/npm. Until they are, install from a clone as shown. Every command below is written to work
from a checkout today.

---

## 1. Developer - call the library from your own code

Use this if you install the packages and call the API directly in Python or Node/TypeScript.

### Install (from a clone)

```bash
git clone https://github.com/Vervelio-Labs/OpenOM
cd OpenOM

# Python
pip install -e core          # the library; add -e cli for the `om` command
# once published: pip install openom-core

# Node / TypeScript
npm install ./js             # builds itself on install (runs its `prepare` build; needs its devDeps)
# once published: npm install openom-js
```

### Run the end-to-end sample (Python)

```bash
python examples/quickstart.py
```

It embeds → reads → validates a committed sample payload against a blank stand-in PDF and prints the
result - no edits, no network, no inference. Source: [`examples/quickstart.py`](../examples/quickstart.py).

### Minimal Python - embed, read, validate

The stable surface is re-exported from the package root:

```python
from openom_core import embed, read, validate

pdf_bytes = open("offering.pdf", "rb").read()
payload   = {...}   # your deal payload (see spec/samples/valid-stnl.json for a valid starter)

# embed (page content is never changed - the output is byte-identical to the eye)
embedded = embed(pdf_bytes, payload, asserted_date="2026-08-16")
open("offering.openom.pdf", "wb").write(embedded)

# read + integrity-verify
r = read(embedded)
print(r.present, r.hash_valid)     # True True  - ReadResult(.present, .payload, .hash_valid, ...)
if r.present and r.hash_valid:
    deal = r.payload["deal"]

# validate against the bundled 0.1 schema (no --schema / no file path needed)
report = validate(r.payload)       # Report(.ok, .errors, .warnings, .info)
if not report.ok:                  # .ok is False when there are error-tier findings
    for f in report.errors:
        print(f.code, f.path, f.message)   # schema errors block; warnings never do
```

### Minimal TypeScript - same operations, byte-parity with Python

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { embedPayload, readPayloadFromBytes, validatePayload } from "openom-js";

const pdf = new Uint8Array(readFileSync("offering.pdf"));
const payload = JSON.parse(readFileSync("deal.json", "utf8"));

// embed (async; page content untouched)
writeFileSync("offering.openom.pdf", await embedPayload(pdf, payload));

// read + verify
const r = await readPayloadFromBytes(new Uint8Array(readFileSync("offering.openom.pdf")));
if (r.state === "present" && r.verification.hashValid) useIt(r.payload);

// validate (the 0.1 schema is bundled)
const { errors } = validatePayload(payload);   // errors[] block; warnings/info never do
if (errors.length) process.exit(1);
```

> **Field-name difference between the cores:** Python `read()` returns `.present` / `.hash_valid`;
> the JS `readPayloadFromBytes()` returns `.state` (`"present"` \| `"absent"` \| `"hash-mismatch"` \| …)
> and `.verification.hashValid`. Both produce the same RFC-8785 canonical JSON and the same SHA-256
> integrity hash (the anti-fork guarantee).

### The CLI (`om`) - no code needed

`pip install -e core -e cli` gives you the `om` command. Verified subcommands:

```bash
om init     deal.json                          # scaffold a ready-to-edit, schema-valid payload
om profile  set --broker "Jane" --brokerage "Acme" --license "MI 1"  # save identity once; auto-filled
om inspect  offering.pdf                       # is there a payload? attachment/marker facts
om embed    offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16
om read     out.pdf                            # print the embedded payload + integrity state
om validate deal.json                          # schema 0.1 is bundled; --schema only to override it
om check    deal.json                          # schema + consistency findings
om extract  offering.pdf                        # deterministic text/image extraction
om embed-batch      --dir ./catalog ...         # bulk-embed a back-catalog
om buildout-manifest ...                        # Buildout listing → openOM payload manifest
om buildout-pull     ...                        # pull from a Buildout MCP connector
om conformance                                  # verify your install reproduces the pinned vectors
```

`deal.json` is the deal data you supply - run **`om init`** to scaffold a valid starter (it stamps
today's date and fills your saved `om profile`), then edit the values. Every `om` error explains the
next step in plain English, and `om` with no command routes non-developers to the browser tool.
(`--schema` is optional: omit it to use the bundled 0.1 schema; pass a path only to override it.)

**Full developer docs:** <https://openom.app/docs/quickstart-developer.html> · package READMEs in
[`core/`](../core), [`cli/`](../cli), [`js/`](../js) · runnable snippets in [`examples/`](../examples).

---

## 2. Portal - trust badges + reading payloads at scale

Use this if you run a listings/CRE site and want a verification badge next to each listing, or want
to read openOM payloads programmatically.

### Option A - the drop-in badge (client-side, zero backend)

```html
<script src="https://openom.app/widget/openom-badge.js" defer></script>

<!-- integrity badge: proves the payload is unaltered since embed -->
<openom-badge src="https://cdn.example.com/listings/123/deal.pdf"></openom-badge>

<!-- add a mirror on the SAME registrable domain to reach ✓✓ Origin-verified -->
<openom-badge
  src="https://broker.example.com/deal.pdf"
  mirror="https://broker.example.com/deal.json"
  details="https://broker.example.com/listing/123"
></openom-badge>
```

The badge re-fetches the PDF bytes itself and runs the exact same `openom-js` read/verify path the
extension uses - so the PDF host must allow the fetch (same-origin, or `Access-Control-Allow-Origin`
on cross-origin PDFs). It fails **closed**: any CORS/network/parse error renders nothing.

Badge states: `absent`/`encrypted` → nothing · `hash-mismatch` → ⚠ Altered payload · `integrity-ok`
→ ✓ Unaltered since embed · `origin-verified` → ✓✓ Origin-verified.

> **Origin-verified needs a same-domain mirror.** `origin-verified` requires the `mirror` JSON to
> live on the **same registrable domain** as the PDF `src` (§10.1). A PDF served from a separate CDN
> domain (`cdn.example.com`) will show `integrity-ok` but never `origin-verified` - host the mirror
> on the listing's own domain to reach ✓✓.
>
> **Badge blank?** Open devtools; a CORS error on the PDF host is the usual cause. For results grids,
> prefer the precompute path below.

### Option B - precompute the state server-side (recommended for results grids)

Call the public `om_read` endpoint once per listing at index time, then render a plain badge with a
fixed `state`. Note that `om_read` returns `state: "present"` - that is **not** a badge state, so map
it before passing it to `<openom-badge>`:

```bash
curl -s https://mcp.openom.app/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"om_read","arguments":{"url":"https://broker.example.com/deal.pdf"}}}'
```

The two fields that drive the badge are `state` and `verification.hashValid`. Map them explicitly:

```js
// r = the om_read structuredContent object
const badge =
  r.state === "present" && r.verification.hashValid ? "integrity-ok" :
  r.state === "hash-mismatch"                       ? "hash-mismatch" :
                                                       "absent";
// then render: <openom-badge state="${badge}"></openom-badge>
```

(Do **not** pass `om_read`'s `"present"` straight into the `state` attribute - the widget maps any
unknown value to `absent` and renders nothing.)

### Option C - read payloads in your own Node code

```ts
import { readPayloadFromBytes, summarizeDeal } from "openom-js";

const r = await readPayloadFromBytes(pdfBytes);
if (r.state === "present" && r.verification.hashValid) {
  const summary = summarizeDeal(r.payload);   // compact, display-ready deal summary
}
```

Change-notification webhooks (§Y): copy [`js/examples/webhook-receiver.ts`](../js/examples/webhook-receiver.ts)
(verify signature → validate envelope → verify `payloadHash` → SSRF-guard `sourceUrl` → dedupe by
event id) and repoint its one import to `openom-js`.

**Full portal docs:** <https://openom.app/docs/quickstart-portal.html> · widget source +
README in [`js/widget/`](../js/widget).

---

## 3. AI-builder - ground an agent on the public MCP endpoint

Use this to point any MCP client at openOM so an agent can read and validate OM PDFs with zero
inference on the server side.

### The public endpoint (no install, no key, no cost)

```
https://mcp.openom.app/mcp
```

It is a deterministic, read-only Cloudflare Worker exposing **two** tools:

- **`om_read`** - read the embedded payload from PDF bytes or an `https` URL; returns
  `state`, `payloadHash`, `verification.hashValid`, the full `payload`, and a compact summary line.
- **`om_validate`** - schema + consistency check of a payload (`ok`, `errors`, `warnings`, `info`).

### Config (Streamable-HTTP clients - Claude Code, Cursor)

The file the README links, [`examples/mcp-config.json`](../examples/mcp-config.json):

```json
{
  "mcpServers": {
    "openom": {
      "url": "https://mcp.openom.app/mcp"
    }
  }
}
```

Paste this into your client's MCP settings - Claude Code / Cursor infer Streamable HTTP from the
`url`. Some strict clients want an explicit `"type": "http"` alongside `url`.

### Config (stdio-only clients - e.g. Claude Desktop's JSON config)

A bare `url` entry is silently ignored by stdio-only clients. Use the `mcp-remote` bridge instead:

```json
{
  "mcpServers": {
    "openom": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.openom.app/mcp"]
    }
  }
}
```

Where it goes: Claude Desktop → `claude_desktop_config.json`; Cursor → Settings › MCP › Add;
Claude.ai/ChatGPT → add a custom connector with the URL.

### Self-host the full six-tool surface

The public endpoint is `om_read` + `om_validate` only. To get the complete deterministic surface -
**`om_inspect · om_extract_text · om_extract_images · om_read · om_validate · om_embed`** - self-host
from a clone:

```bash
pip install -e ./core && pip install -e ./mcp     # not yet on PyPI; from a checkout
# once published: pip install openom-mcp

om-mcp          # stdio transport
om-mcp-http     # hosted Streamable HTTP transport
```

Then point your client's config at `{ "command": "om-mcp" }` (stdio) or the `om-mcp-http` URL.

> The server contains **zero inference**, always - it grounds an agent on verifiable, hash-checked
> facts. "Verified" means provenance (who asserted it, unaltered, as of when), not market truth.

**Full AI-builder docs:** <https://openom.app/docs/grounding-ai.html>.
