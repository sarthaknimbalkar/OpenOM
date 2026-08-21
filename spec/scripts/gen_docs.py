#!/usr/bin/env python3
"""Generate the per-persona docs site pages (#141), served under /openom/docs/.

WHY: the single Python quick-start serves none of the three real audiences — a
broker wanting to publish an OM, a portal integrator wanting to consume, and a
third-party implementer building against the standard. Worldwide adoption needs an
on-ramp per audience plus a *reference* that cannot lie: the field table and the
error-code catalog are generated straight from ``om-0.1.schema.json`` and
``codes.json``, so they can never drift from what the validator actually enforces.

Imported by ``gen_site.py`` (one drift gate covers the whole ``site/`` tree). Pure:
returns ``{relative_path: html}`` — no I/O, deterministic ordering.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent


def _page(title: str, body: str) -> str:
    """Wrap page body in the shared, dependency-free shell (matches the ns landing)."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} · openOM docs</title>
  <style>
    body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 52rem; margin: 2.5rem auto;
            padding: 0 1rem; color: #111; }}
    a {{ color: #065f46; }}
    code {{ background: #f4f4f5; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.9em; }}
    pre {{ background: #0b1021; color: #e6edf3; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
    pre code {{ background: none; color: inherit; padding: 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.92em; }}
    th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #e5e7eb;
              vertical-align: top; }}
    th {{ background: #f9fafb; }}
    nav.crumbs {{ font-size: 0.9em; margin-bottom: 1.5rem; }}
    .cards {{ display: grid; gap: 1rem; grid-template-columns: 1fr; }}
    @media (min-width: 40rem) {{ .cards {{ grid-template-columns: 1fr 1fr 1fr; }} }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 1rem 1.1rem; }}
    .card h3 {{ margin: 0 0 0.3rem; }}
    .sev-error {{ color: #7f1d1d; font-weight: 600; }}
    .sev-warning {{ color: #92400e; }}
    .sev-info {{ color: #374151; }}
    .req {{ color: #b91c1c; font-weight: 600; }}
  </style>
</head>
<body>
  <nav class="crumbs"><a href="/openom/">openOM</a> · <a href="/openom/docs/">docs</a></nav>
{body}
</body>
</html>
"""


def _docs_index() -> str:
    body = """
  <h1>openOM docs</h1>
  <p>Machine-readable, broker-asserted data embedded in CRE offering memoranda —
     extracted once at the source, consumed cheaply everywhere. Pick your on-ramp:</p>
  <div class="card" style="border-color:#065f46;background:#ecfdf5;">
    <h3 style="margin-top:0;">🤖 Building an AI agent for CRE? Start here</h3>
    <p>Ground your agent in <b>verified facts, not guesses</b> — a deterministic read of a
       broker-asserted, hash-verified opinion instead of a hallucination-prone re-parse of the PDF.
       <a href="/openom/docs/grounding-ai.html"><b>Grounding AI agents in openOM →</b></a></p>
  </div>
  <div class="cards">
    <div class="card">
      <h3>Broker / author</h3>
      <p>You have OM PDFs and want them to carry structured, verifiable data.</p>
      <p><a href="/openom/docs/quickstart-broker.html">10-minute quick-start →</a></p>
    </div>
    <div class="card">
      <h3>Portal / consumer</h3>
      <p>You want to read and trust openOM data on PDFs you receive or host.</p>
      <p><a href="/openom/docs/quickstart-portal.html">10-minute quick-start →</a></p>
    </div>
    <div class="card">
      <h3>Implementer / developer</h3>
      <p>You are building against the standard in your own language or pipeline.</p>
      <p><a href="/openom/docs/quickstart-developer.html">10-minute quick-start →</a></p>
    </div>
  </div>
  <h2>Reference</h2>
  <ul>
    <li><a href="/openom/docs/schema-reference.html">Payload field reference</a>
        — generated from the JSON Schema.</li>
    <li><a href="/openom/docs/codes.html">Validation code catalog</a>
        — every error/warning/info code the validator emits.</li>
    <li><a href="/openom/verify/">Verify a PDF</a>
        — drop a PDF and check its openOM state, entirely in your browser.</li>
    <li><a href="/openom/spec/om-0.1.schema.json">Raw JSON Schema</a> ·
        <a href="/openom/ns/0.1">JSON-LD context</a></li>
  </ul>
  <p><small>An OM is an <b>advertisement</b> — a broker's <b>opinion of value</b>, agreed to by the
     seller before publication. openOM records who asserted it, unaltered, and as of when; it never
     claims the opinion is true. <b>Verified means provenance, not truth.</b> The engine is
     deterministic and inference-free; every payload is an identified party's opinion as of a date —
     assertions, never facts.</small></p>
"""
    return _page("Overview", body)


def _quickstart_broker() -> str:
    body = """
  <h1>Quick-start · broker / author</h1>
  <p>Goal: turn an existing OM PDF into an openOM PDF that carries a verifiable,
     broker-asserted payload — without changing a single visible pixel.</p>
  <h2>Option A — the browser extension (no install of a toolchain)</h2>
  <p>Load the extension (Chrome 116+), open your OM, use <em>author mode</em> to review
     the extracted fields, then <strong>assert</strong> and embed. You review every field
     before it is stamped with your name and the date — the review panel is the assertion
     gate. Extraction (if you use on-device assist) never leaves your machine.</p>
  <h2>Option B — the CLI (scriptable / server-side)</h2>
  <pre><code>pip install openom-core openom-cli

om embed offering.pdf --payload deal.json --out offering.openom.pdf --asserted-date 2026-08-18
om read  offering.openom.pdf          # confirm the payload round-trips
om validate deal.json                 # schema errors block; consistency warnings never do</code></pre>
  <p>Every payload needs <code>assertedBy</code> + <code>assertedDate</code> and an
     <code>noiType</code> (<code>in-place</code> or <code>pro-forma</code>). Re-embedding
     <em>replaces</em> (never stacks) and records <code>meta.supersedes</code>.</p>
  <p>Next: the <a href="/openom/docs/schema-reference.html">field reference</a> for exactly
     what goes in <code>deal.json</code>.</p>
"""
    return _page("Broker quick-start", body)


def _quickstart_portal() -> str:
    body = """
  <h1>Quick-start · portal / consumer</h1>
  <p>Goal: read and trust openOM data on PDFs you host or receive — with an honest badge,
     never overclaiming.</p>
  <h2>Drop-in badge (one script tag)</h2>
  <pre><code>&lt;script src="https://verveliolabs.com/openom/widget/openom-badge.js" defer&gt;&lt;/script&gt;
&lt;openom-badge src="https://cdn.example.com/deal.pdf"&gt;&lt;/openom-badge&gt;</code></pre>
  <p>The badge re-fetches the bytes and runs the deterministic read/verify path. It shows
     <em>Unaltered since embed</em> for integrity, <em>Origin-verified</em> only when a
     same-domain mirror matches, and <em>nothing</em> when there is no payload.</p>
  <h2>In your own code (Node)</h2>
  <pre><code>import { readPayloadFromBytes } from "openom-js";
const r = await readPayloadFromBytes(pdfBytes);
if (r.state === "present" &amp;&amp; r.verification.hashValid) useIt(r.payload);</code></pre>
  <p>Change notifications: verify webhook deliveries with the
     <a href="https://github.com/sarthaknimbalkar/OpenOM/blob/main/js/examples/webhook-receiver.ts">reference receiver</a>
     — signature → envelope → payloadHash binding, in that order.</p>
"""
    return _page("Portal quick-start", body)


def _quickstart_developer() -> str:
    body = """
  <h1>Quick-start · implementer / developer</h1>
  <p>Goal: build against the standard and stay byte-compatible with the reference cores.</p>
  <h2>The contract</h2>
  <ul>
    <li><a href="/openom/spec/om-0.1.schema.json">Payload schema</a> (JSON Schema 2020-12) and the
        <a href="/openom/ns/0.1">JSON-LD context</a>.</li>
    <li>Canonicalization is <strong>RFC 8785 (JCS)</strong>; the integrity hash is SHA-256 over the
        canonical bytes. This is the anti-fork keystone — two conformant implementations MUST produce
        byte-identical canonical JSON and the same hash.</li>
    <li>The <a href="https://github.com/sarthaknimbalkar/OpenOM/tree/main/spec/vectors">conformance
        vectors</a> are the oracle: canonical bytes, hashes, golden embedded PDFs, negatives, and a
        differential-fuzz corpus. Reproduce them exactly.</li>
  </ul>
  <h2>Reference implementations</h2>
  <pre><code>pip install openom-core     # Python: embed/read/inspect/extract/validate
npm  install openom-js       # TypeScript: byte-parity with the Python core</code></pre>
  <h2>Validation model</h2>
  <p>Two tiers: <strong>schema errors block</strong>; <strong>consistency warnings never block</strong>;
     market truth is out of scope forever. See the
     <a href="/openom/docs/codes.html">code catalog</a> for every code and its requirement clause.</p>
"""
    return _page("Developer quick-start", body)


def _resolve(schema: dict, node: dict) -> dict:
    """Resolve a local ``$ref`` into $defs one hop (enough for the reference table)."""
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return schema.get("$defs", {}).get(ref.split("/")[-1], node)
    return node


def _type_of(node: dict) -> str:
    if "$ref" in node:
        return node["$ref"].split("/")[-1]
    t = node.get("type")
    if isinstance(t, list):
        return " | ".join(t)
    if t == "array":
        items = node.get("items", {})
        inner = items.get("$ref", "").split("/")[-1] or items.get("type", "any")
        return f"array&lt;{inner}&gt;"
    if node.get("enum"):
        return "enum(" + ", ".join(map(str, node["enum"])) + ")"
    return t or "any"


def _rows(schema: dict, node: dict, prefix: str, required: set[str], depth: int) -> list[str]:
    out: list[str] = []
    props = node.get("properties", {})
    for name, raw in props.items():
        child = _resolve(schema, raw)
        path = f"{prefix}{name}"
        req = "✓" if name in required else ""
        desc = html.escape(str(raw.get("description") or child.get("description") or ""))
        out.append(
            f"<tr><td><code>{html.escape(path)}</code></td>"
            f"<td>{_type_of(raw)}</td><td>{req}</td><td>{desc}</td></tr>"
        )
        # One level of nesting keeps the table legible while covering the shaped objects.
        if depth < 2 and (child.get("type") == "object" or "properties" in child):
            sub_req = set(child.get("required", []))
            out += _rows(schema, child, f"{path}.", sub_req, depth + 1)
    return out


def _schema_reference() -> str:
    schema = json.loads((SPEC / "om-0.1.schema.json").read_text("utf-8"))
    rows = _rows(schema, schema, "", set(schema.get("required", [])), 0)
    body = f"""
  <h1>Payload field reference</h1>
  <p>Generated from <code>om-0.1.schema.json</code> ({html.escape(schema.get('title', ''))}).
     <span class="req">✓</span> marks required fields.</p>
  <table>
    <thead><tr><th>Field</th><th>Type</th><th>Req</th><th>Description</th></tr></thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
"""
    return _page("Field reference", body)


def _codes_catalog() -> str:
    data = json.loads((SPEC / "codes.json").read_text("utf-8"))
    codes = data["codes"]
    rows = []
    for code, meta in codes.items():
        sev = meta["severity"]
        rows.append(
            f'<tr><td><code>{html.escape(code)}</code></td>'
            f'<td class="sev-{sev}">{sev}</td>'
            f'<td><code>{html.escape(meta["requirement"])}</code></td></tr>'
        )
    body = f"""
  <h1>Validation code catalog</h1>
  <p>Every code the validator can emit, from <code>codes.json</code> (the single registry both
     cores drift-lock to). <strong>error</strong> blocks; <strong>warning</strong> and
     <strong>info</strong> never block.</p>
  <table>
    <thead><tr><th>Code</th><th>Severity</th><th>Requirement</th></tr></thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
"""
    return _page("Code catalog", body)


def _verify_tool() -> str:
    # A hosted, fully client-side "drop a PDF -> see its openOM state" tool (#145). Bytes never
    # leave the browser: it reads the file locally via the deployed widget bundle's window.openOM.
    body = """
  <h1>Verify an openOM PDF</h1>
  <p>Drop or choose a PDF. It is read <strong>entirely in your browser</strong> — the bytes never
     leave your machine — and checked for an embedded, unaltered openOM payload.</p>
  <p><input type="file" id="f" accept="application/pdf,.pdf" /></p>
  <div id="badge" style="margin:1rem 0;"></div>
  <pre id="out" hidden></pre>
  <script src="/openom/widget/openom-badge.js" defer></script>
  <script>
    const f = document.getElementById("f");
    const out = document.getElementById("out");
    const badge = document.getElementById("badge");
    f.addEventListener("change", async () => {
      const file = f.files && f.files[0];
      if (!file || !window.openOM) return;
      const bytes = new Uint8Array(await file.arrayBuffer());
      const r = await window.openOM.readPayloadFromBytes(bytes);
      const present = r.state === "present" || r.state === "hash-mismatch";
      const view = window.openOM.computeBadge({
        present,
        hashValid: r.verification.hashValid,
        originVerified: false,
        signatureValid: r.verification.signatureValid,
      });
      badge.textContent = view.state === "absent" ? "No openOM data in this PDF." : view.label + " — " + view.caption;
      if (r.payload) { out.hidden = false; out.textContent = JSON.stringify(r.payload, null, 2); }
      else { out.hidden = true; }
    });
  </script>
  <p><small>Origin verification (the domain-vouch layer) needs a hosted mirror and isn't available
     for a local file; this tool shows integrity only. For a live page, use the
     <a href="/openom/docs/quickstart-portal.html">embeddable badge</a>.</small></p>
"""
    return _page("Verify a PDF", body)


def _grounding_ai() -> str:
    body = """
  <h1>Grounding AI agents in openOM</h1>
  <p>General-purpose AI extraction of an offering memorandum <b>hallucinates</b> — it will
     confidently invent an NOI, a cap rate, or a lease term that looks right and isn't. In CRE that
     is a liability, not a convenience. openOM removes the guess: for an openOM-enabled OM your agent
     reads a <b>broker-asserted, hash-verified</b> payload deterministically — no vision parse, no
     re-extraction, no hallucination.</p>

  <h2>The one thing to get right: it's an opinion, not a fact</h2>
  <p>An OM is an <b>advertisement</b> — the broker's <b>opinion of value</b>, agreed to by the seller
     before publication. So openOM tells your agent <i>who</i> asserted a figure, that it is
     <i>unaltered</i>, and <i>as of when</i> — <b>never that it is true</b>. Ground the model on
     <i>"the broker asserted NOI = $143,750, unaltered, as of 2026-05-31"</i>, never <i>"NOI is
     $143,750."</i> <b>Verified means provenance, not truth.</b> Underwriting still happens at the
     deal desk off the broker-of-record file.</p>

  <h2>Connect the deterministic MCP server</h2>
  <p>openOM ships a deterministic <a href="https://github.com/sarthaknimbalkar/OpenOM/tree/main/mcp">MCP
     server</a> — six read/validate/inspect tools, <b>zero inference, no API key, no per-call
     cost</b>. Point your MCP client at it (stdio locally, or a hosted deterministic instance):</p>
  <pre><code>{ "mcpServers": { "openom": { "command": "om-mcp" } } }</code></pre>
  <p>Then the agent uses:</p>
  <ul>
    <li><code>om_read</code> — the broker-asserted payload + <code>verification.hashValid</code>
        (unaltered since embed). A hash-mismatched payload is returned as null — never trust it.</li>
    <li><code>om_validate</code> — schema + internal-consistency (NOI÷price vs cap rate, rent-schedule
        math). Validity means well-formed and self-consistent, <b>not</b> that the opinion is right.</li>
    <li><code>om_inspect</code> · <code>om_extract_text</code> · <code>om_extract_images</code> —
        classify, and pull text/images for the OMs that aren't openOM-enabled yet.</li>
  </ul>

  <h2>Tell your agent how to treat it (system-prompt snippet)</h2>
  <pre><code>When an openOM payload is present, use it as the broker's ASSERTED OPINION, not fact.
- Attribute every figure: "&lt;assertedBy&gt; asserts &lt;field&gt; = &lt;value&gt;, as of &lt;assertedDate&gt;".
- If verification.hashValid is not true, do NOT use the payload — it may be altered.
- Never state an OM figure as verified truth; it is an advertisement / opinion of value.
- For OMs with no openOM payload, extraction is a guess — flag it as unverified.</code></pre>

  <h2>Why this beats re-extraction</h2>
  <ul>
    <li><b>No hallucination</b> — the figure is transcribed once at the source and hash-locked.</li>
    <li><b>Defensible</b> — provenance (who/unaltered/as-of-when) is exactly what credit committees
        and compliance need; "the AI guessed" is not.</li>
    <li><b>Free + instant</b> — a deterministic read, not a per-document inference bill.</li>
    <li><b>Honest by design</b> — the badge/labels never say "verified" to mean "true".</li>
  </ul>
  <p><small>Cold-start reality: most OMs aren't openOM-enabled yet, so your agent still needs an
     extractor for those — treat that output as an unverified guess, and prefer openOM-enabled OMs as
     the trusted path. See the <a href="/openom/docs/quickstart-developer.html">developer
     quick-start</a> and the <a href="/openom/verify/">verify tool</a>.</small></p>
"""
    return _page("Grounding AI agents", body)


def docs_pages() -> dict[str, str]:
    """Return ``{relative_path_under_site: html}`` for the whole docs tree. Deterministic."""
    return {
        "openom/verify/index.html": _verify_tool(),
        "openom/docs/index.html": _docs_index(),
        "openom/docs/grounding-ai.html": _grounding_ai(),
        "openom/docs/quickstart-broker.html": _quickstart_broker(),
        "openom/docs/quickstart-portal.html": _quickstart_portal(),
        "openom/docs/quickstart-developer.html": _quickstart_developer(),
        "openom/docs/schema-reference.html": _schema_reference(),
        "openom/docs/codes.html": _codes_catalog(),
    }
