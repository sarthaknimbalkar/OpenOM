#!/usr/bin/env python3
"""Generate the per-persona docs site pages (#141), served under /docs/.

WHY: the single Python quick-start serves none of the three real audiences - a
broker wanting to publish an OM, a portal integrator wanting to consume, and a
third-party implementer building against the standard. Worldwide adoption needs an
on-ramp per audience plus a *reference* that cannot lie: the field table and the
error-code catalog are generated straight from ``om-0.1.schema.json`` and
``codes.json``, so they can never drift from what the validator actually enforces.

Imported by ``gen_site.py`` (one drift gate covers the whole ``site/`` tree). Pure:
returns ``{relative_path: html}`` - no I/O, deterministic ordering.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent


SITE = "https://openom.app"
ORG = {"@type": "Organization", "name": "Vervelio Labs", "url": "https://verveliolabs.com"}


def _jsonld(*objs: dict | None) -> str:
    """Render schema.org objects as JSON-LD <script> blocks (SEO/AEO/GEO structured data)."""
    import json as _json

    return "\n".join(
        f'  <script type="application/ld+json">{_json.dumps(o, ensure_ascii=False)}</script>'
        for o in objs
        if o
    )


def _breadcrumb(canonical: str, title: str) -> dict:
    items = [{"@type": "ListItem", "position": 1, "name": "openOM", "item": SITE + "/"}]
    if canonical != "/":
        items.append({"@type": "ListItem", "position": 2, "name": "Docs", "item": SITE + "/docs/"})
        if canonical != "/docs/":
            items.append(
                {"@type": "ListItem", "position": 3, "name": title, "item": SITE + canonical}
            )
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def _article(title: str, description: str, canonical: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": title,
        "description": description,
        "url": SITE + canonical,
        "inLanguage": "en",
        "author": ORG,
        "publisher": ORG,
        "isPartOf": {"@type": "WebSite", "name": "openOM", "url": SITE + "/"},
        "about": "commercial real estate offering memorandum machine-readable data standard",
    }


def _faqpage(qas: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qas
        ],
    }


def _page(
    title: str,
    body: str,
    *,
    description: str = "",
    canonical: str = "/",
    jsonld: str = "",
    seo_title: str = "",
) -> str:
    """Wrap page body in the shared shell with full SEO/AEO/GEO metadata: description, canonical,
    Open Graph, Twitter card, and JSON-LD structured data. ``seo_title`` (search-intent phrasing)
    drives the <title> + og/twitter title; the in-body h1 keeps the short ``title``.
    Dependency-free; deterministic."""
    url = SITE + canonical
    desc = html.escape(description)
    head_title = html.escape(seo_title) if seo_title else f"{html.escape(title)} · openOM docs"
    og_title = html.escape(seo_title) if seo_title else html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{head_title}</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{url}" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="openOM" />
  <meta property="og:title" content="{og_title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{SITE}/og.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{og_title}" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{SITE}/og.png" />
{jsonld}
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
  <nav class="crumbs"><a href="/">openOM</a> · <a href="/docs/">docs</a></nav>
{body}
</body>
</html>
"""


def _docs_index() -> str:
    body = """
  <h1>openOM docs</h1>
  <p>Machine-readable, broker-asserted data embedded in CRE offering memoranda -
     extracted once at the source, consumed cheaply everywhere. Pick your on-ramp:</p>
  <div class="card" style="border-color:#065f46;background:#ecfdf5;">
    <h3 style="margin-top:0;">🤖 Building an AI agent for CRE? Start here</h3>
    <p>Ground your agent in <b>verified facts, not guesses</b> - a deterministic read of a
       broker-asserted, hash-verified opinion instead of a hallucination-prone re-parse of the PDF.
       <a href="/docs/grounding-ai.html"><b>Grounding AI agents in openOM →</b></a></p>
  </div>
  <div class="cards">
    <div class="card">
      <h3>Broker / author</h3>
      <p>You have OM PDFs and want them to carry structured, verifiable data.</p>
      <p><a href="/docs/quickstart-broker.html">10-minute quick-start →</a></p>
    </div>
    <div class="card">
      <h3>Portal / consumer</h3>
      <p>You want to read and trust openOM data on PDFs you receive or host.</p>
      <p><a href="/docs/quickstart-portal.html">10-minute quick-start →</a></p>
    </div>
    <div class="card">
      <h3>Implementer / developer</h3>
      <p>You are building against the standard in your own language or pipeline.</p>
      <p><a href="/docs/quickstart-developer.html">10-minute quick-start →</a></p>
    </div>
  </div>
  <h2>Learn</h2>
  <ul>
    <li><a href="/docs/what-is-an-offering-memorandum.html">What is an offering memorandum?</a>
        - the definition, what an OM contains, and why its data is an assertion.</li>
  </ul>
  <h2>Reference</h2>
  <ul>
    <li><a href="/docs/schema-reference.html">Payload field reference</a>
        - generated from the JSON Schema.</li>
    <li><a href="/docs/codes.html">Validation code catalog</a>
        - every error/warning/info code the validator emits.</li>
    <li><a href="/verify/">Verify a PDF</a>
        - drop a PDF and check its openOM state, entirely in your browser.</li>
    <li><a href="/spec/om-0.1.schema.json">Raw JSON Schema</a> ·
        <a href="/ns/0.1">JSON-LD context</a></li>
  </ul>
  <p><small>An OM is an <b>advertisement</b> - a broker's <b>opinion of value</b>, agreed to by the
     seller before publication. openOM records who asserted it, unaltered, and as of when; it never
     claims the opinion is true. <b>Verified means provenance, not truth.</b> The engine is
     deterministic and inference-free; every payload is an identified party's opinion as of a date -
     assertions, never facts.</small></p>
"""
    faq = [
        (
            "What is openOM?",
            "openOM is an open standard that embeds machine-readable, broker-asserted data inside a "
            "commercial real estate offering memorandum (OM) PDF and mirrors it as JSON-LD, so "
            "buyers, portals, and AI agents read the deal once, verified, without re-extraction.",
        ),
        (
            "Is openOM offering-memorandum data verified as true?",
            "No. An offering memorandum is an advertisement, the broker's opinion of value. openOM "
            "proves who asserted the data, that it is unaltered, and as of when. Verified means "
            "provenance, not truth.",
        ),
        (
            "How do I read openOM data from a PDF?",
            "Read it deterministically with openom-js or openom-core, the om CLI, or the openOM MCP "
            "server. No AI, no keys, no per-document cost; the embedded om.json is hash-verified.",
        ),
        (
            "Does openOM use AI or LLMs?",
            "No. The engine is deterministic and inference-free. AI assists only the broker at "
            "authoring time, on-device; reading and verifying never use AI.",
        ),
        (
            "How do I add openOM data to my offering memoranda?",
            "Use the browser extension author mode or the om CLI to review, assert, and embed a "
            "payload. The output PDF stays visually identical.",
        ),
    ]
    desc = (
        "openOM is an open standard for machine-readable, broker-asserted, hash-verified data in "
        "commercial real estate offering memoranda (OMs), mirrored as JSON-LD for buyers, portals, "
        "and AI agents."
    )
    return _page(
        "Overview",
        body,
        description=desc,
        canonical="/docs/",
        jsonld=_jsonld(_article("openOM documentation", desc, "/docs/"), _breadcrumb("/docs/", "Docs"), _faqpage(faq)),
        seo_title="openOM docs - machine-readable data for CRE offering memoranda",
    )


def _quickstart_broker() -> str:
    body = """
  <h1>Quick-start · broker / author</h1>
  <p>Goal: turn an existing OM PDF into an openOM PDF that carries a verifiable,
     broker-asserted payload - without changing a single visible pixel.</p>
  <h2>Option A - the browser extension (no install of a toolchain)</h2>
  <p>Load the extension (Chrome 116+), open your OM, use <em>author mode</em> to review
     the extracted fields, then <strong>assert</strong> and embed. You review every field
     before it is stamped with your name and the date - the review panel is the assertion
     gate. Extraction (if you use on-device assist) never leaves your machine.</p>
  <h2>Option B - the CLI (scriptable / server-side)</h2>
  <pre><code>pip install openom-core openom-cli

om embed offering.pdf --payload deal.json --out offering.openom.pdf --asserted-date 2026-08-18
om read  offering.openom.pdf          # confirm the payload round-trips
om validate deal.json                 # schema errors block; consistency warnings never do</code></pre>
  <p>Every payload needs <code>assertedBy</code> + <code>assertedDate</code> and an
     <code>noiType</code> (<code>in-place</code> or <code>pro-forma</code>). Re-embedding
     <em>replaces</em> (never stacks) and records <code>meta.supersedes</code>.</p>
  <p>Next: the <a href="/docs/schema-reference.html">field reference</a> for exactly
     what goes in <code>deal.json</code>.</p>
"""
    _d = 'Turn an offering memorandum PDF into an openOM PDF carrying verifiable, broker-asserted data, via the browser extension or the om CLI. The output is visually identical.'
    return _page("Broker quick-start", body, description=_d, canonical="/docs/quickstart-broker", jsonld=_jsonld(_article("Broker quick-start", _d, "/docs/quickstart-broker"), _breadcrumb("/docs/quickstart-broker", "Broker quick-start")), seo_title="Publish a verifiable offering memorandum - openOM broker quick-start")


def _quickstart_portal() -> str:
    body = """
  <h1>Quick-start · portal / consumer</h1>
  <p>Goal: read and trust openOM data on PDFs you host or receive - with an honest badge,
     never overclaiming.</p>
  <h2>Drop-in badge (one script tag)</h2>
  <pre><code>&lt;script src="https://openom.app/widget/openom-badge.js" defer&gt;&lt;/script&gt;
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
     - signature → envelope → payloadHash binding, in that order.</p>
"""
    _d = 'Read and trust openOM data on offering memoranda you host or receive: the drop-in <openom-badge> widget and the openom-js reader, with an honest trust badge.'
    return _page("Portal quick-start", body, description=_d, canonical="/docs/quickstart-portal", jsonld=_jsonld(_article("Portal quick-start", _d, "/docs/quickstart-portal"), _breadcrumb("/docs/quickstart-portal", "Portal quick-start")), seo_title="Read & trust openOM data on offering memoranda - portal quick-start")


def _quickstart_developer() -> str:
    body = """
  <h1>Quick-start · implementer / developer</h1>
  <p>Goal: build against the standard and stay byte-compatible with the reference cores.</p>
  <h2>The contract</h2>
  <ul>
    <li><a href="/spec/om-0.1.schema.json">Payload schema</a> (JSON Schema 2020-12) and the
        <a href="/ns/0.1">JSON-LD context</a>.</li>
    <li>Canonicalization is <strong>RFC 8785 (JCS)</strong>; the integrity hash is SHA-256 over the
        canonical bytes. This is the anti-fork keystone - two conformant implementations MUST produce
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
     <a href="/docs/codes.html">code catalog</a> for every code and its requirement clause.</p>
"""
    _d = 'Build against the openOM standard: JSON Schema, JSON-LD @context, RFC 8785 canonicalization, conformance vectors, and byte-parity Python and TypeScript reference implementations.'
    return _page("Developer quick-start", body, description=_d, canonical="/docs/quickstart-developer", jsonld=_jsonld(_article("Developer quick-start", _d, "/docs/quickstart-developer"), _breadcrumb("/docs/quickstart-developer", "Developer quick-start")), seo_title="Build against the openOM standard - developer quick-start")


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
    _d = 'openOM 0.1 payload field reference, generated from the JSON Schema: every property, type, and requirement for commercial real estate offering-memorandum data.'
    return _page("Field reference", body, description=_d, canonical="/docs/schema-reference", jsonld=_jsonld(_article("Field reference", _d, "/docs/schema-reference"), _breadcrumb("/docs/schema-reference", "Field reference")), seo_title="openOM payload field reference (JSON Schema)")


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
    _d = 'openOM validation code catalog: every schema error, consistency warning, and info code the validator emits, with its requirement clause.'
    return _page("Code catalog", body, description=_d, canonical="/docs/codes", jsonld=_jsonld(_article("Code catalog", _d, "/docs/codes"), _breadcrumb("/docs/codes", "Code catalog")), seo_title="openOM validation codes - errors, warnings & info reference")


def _verify_tool() -> str:
    # A hosted, fully client-side "drop a PDF -> see its openOM state" tool (#145). Bytes never
    # leave the browser: it reads the file locally via the deployed widget bundle's window.openOM.
    body = """
  <h1>Verify an openOM PDF</h1>
  <p>Drop or choose a PDF. It is read <strong>entirely in your browser</strong> - the bytes never
     leave your machine - and checked for an embedded, unaltered openOM payload.</p>
  <p><input type="file" id="f" accept="application/pdf,.pdf" /></p>
  <div id="badge" style="margin:1rem 0;"></div>
  <pre id="out" hidden></pre>
  <script src="/widget/openom-badge.js" defer></script>
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
      badge.textContent = view.state === "absent" ? "No openOM data in this PDF." : view.label + " - " + view.caption;
      if (r.payload) { out.hidden = false; out.textContent = JSON.stringify(r.payload, null, 2); }
      else { out.hidden = true; }
    });
  </script>
  <p><small>Origin verification (the domain-vouch layer) needs a hosted mirror and isn't available
     for a local file; this tool shows integrity only. For a live page, use the
     <a href="/docs/quickstart-portal.html">embeddable badge</a>.</small></p>
"""
    _d = 'Verify an openOM offering-memorandum PDF entirely in your browser: check its embedded, unaltered, broker-asserted data. Bytes never leave your machine.'
    return _page("Verify a PDF", body, description=_d, canonical="/verify/", jsonld=_jsonld(_article("Verify a PDF", _d, "/verify/"), _breadcrumb("/verify/", "Verify a PDF")), seo_title="Verify an openOM offering-memorandum PDF in your browser")


def _grounding_ai() -> str:
    body = """
  <h1>Grounding AI agents in openOM</h1>
  <p>General-purpose AI extraction of an offering memorandum <b>hallucinates</b> - it will
     confidently invent an NOI, a cap rate, or a lease term that looks right and isn't. In CRE that
     is a liability, not a convenience. openOM removes the guess: for an openOM-enabled OM your agent
     reads a <b>broker-asserted, hash-verified</b> payload deterministically - no vision parse, no
     re-extraction, no hallucination.</p>

  <h2>The one thing to get right: it's an opinion, not a fact</h2>
  <p>An OM is an <b>advertisement</b> - the broker's <b>opinion of value</b>, agreed to by the seller
     before publication. So openOM tells your agent <i>who</i> asserted a figure, that it is
     <i>unaltered</i>, and <i>as of when</i> - <b>never that it is true</b>. Ground the model on
     <i>"the broker asserted NOI = $143,750, unaltered, as of 2026-05-31"</i>, never <i>"NOI is
     $143,750."</i> <b>Verified means provenance, not truth.</b> Underwriting still happens at the
     deal desk off the broker-of-record file.</p>

  <h2>Connect the deterministic MCP server</h2>
  <p>openOM ships a deterministic <a href="https://github.com/sarthaknimbalkar/OpenOM/tree/main/mcp">MCP
     server</a> - six read/validate/inspect tools, <b>zero inference, no API key, no per-call
     cost</b>. Point your MCP client at it (stdio locally, or a hosted deterministic instance):</p>
  <pre><code>{ "mcpServers": { "openom": { "command": "om-mcp" } } }</code></pre>
  <p>Then the agent uses:</p>
  <ul>
    <li><code>om_read</code> - the broker-asserted payload + <code>verification.hashValid</code>
        (unaltered since embed). A hash-mismatched payload is returned as null - never trust it.</li>
    <li><code>om_validate</code> - schema + internal-consistency (NOI÷price vs cap rate, rent-schedule
        math). Validity means well-formed and self-consistent, <b>not</b> that the opinion is right.</li>
    <li><code>om_inspect</code> · <code>om_extract_text</code> · <code>om_extract_images</code> -
        classify, and pull text/images for the OMs that aren't openOM-enabled yet.</li>
  </ul>

  <h2>Tell your agent how to treat it (system-prompt snippet)</h2>
  <pre><code>When an openOM payload is present, use it as the broker's ASSERTED OPINION, not fact.
- Attribute every figure: "&lt;assertedBy&gt; asserts &lt;field&gt; = &lt;value&gt;, as of &lt;assertedDate&gt;".
- If verification.hashValid is not true, do NOT use the payload - it may be altered.
- Never state an OM figure as verified truth; it is an advertisement / opinion of value.
- For OMs with no openOM payload, extraction is a guess - flag it as unverified.</code></pre>

  <h2>Why this beats re-extraction</h2>
  <ul>
    <li><b>No hallucination</b> - the figure is transcribed once at the source and hash-locked.</li>
    <li><b>Defensible</b> - provenance (who/unaltered/as-of-when) is exactly what credit committees
        and compliance need; "the AI guessed" is not.</li>
    <li><b>Free + instant</b> - a deterministic read, not a per-document inference bill.</li>
    <li><b>Honest by design</b> - the badge/labels never say "verified" to mean "true".</li>
  </ul>
  <p><small>Cold-start reality: most OMs aren't openOM-enabled yet, so your agent still needs an
     extractor for those - treat that output as an unverified guess, and prefer openOM-enabled OMs as
     the trusted path. See the <a href="/docs/quickstart-developer.html">developer
     quick-start</a> and the <a href="/verify/">verify tool</a>.</small></p>
"""
    _d = "Ground your commercial real estate AI agent in verified facts: read an offering memorandum's broker-asserted, hash-verified openOM payload deterministically via MCP instead of hallucination-prone PDF extraction."
    return _page("Grounding AI agents", body, description=_d, canonical="/docs/grounding-ai", jsonld=_jsonld(_article("Grounding AI agents", _d, "/docs/grounding-ai"), _breadcrumb("/docs/grounding-ai", "Grounding AI agents"), _faqpage([('Can I ground an AI agent on offering memorandum data?', 'Yes. Point your MCP client at the openOM server and read a broker-asserted, hash-verified payload via om_read: deterministic ground truth instead of hallucination-prone PDF extraction.'), ('How does openOM reduce AI hallucination in commercial real estate?', 'It replaces per-document AI extraction with one at-source, hash-verified, broker-asserted fact attributed to a named party as of a date, so the model cites provenance instead of guessing.')])), seo_title="Ground AI agents in verified CRE offering-memorandum data - openOM")


def _what_is_om() -> str:
    """Top-of-funnel pillar page: the definitional query 'what is an offering memorandum'. This is the
    query answer engines (Google AI Overviews, Perplexity, ChatGPT) resolve most; a clean DefinedTerm
    + FAQPage page is how openOM gets cited as the authority on OM data - AEO/GEO leverage."""
    canonical = "/docs/what-is-an-offering-memorandum"
    desc = (
        "An offering memorandum (OM) is the marketing document a broker uses to offer a commercial "
        "real estate asset for sale: the property, the deal terms, the tenancy, and the broker's "
        "opinion of value. Learn what an OM contains, why its data is an assertion rather than a "
        "fact, and how openOM makes it machine-readable and verifiable."
    )
    body = """
  <h1>What is an offering memorandum (OM)?</h1>
  <p>An <b>offering memorandum</b> (OM, sometimes "offering memo" or "deal book") is the marketing
     document a commercial real estate (CRE) broker prepares to offer a property for sale to
     prospective buyers. It presents the asset, the deal terms, the tenancy, and the broker's
     <b>opinion of value</b> - typically as a designed PDF of 10-40 pages.</p>

  <h2>What an offering memorandum contains</h2>
  <ul>
    <li><b>The property</b> - address, asset type, building and lot size, year built.</li>
    <li><b>The deal</b> - asking price, capitalization (cap) rate, and net operating income (NOI).</li>
    <li><b>The tenancy</b> - tenant(s), lease type (e.g. NNN), term, and the rent schedule.</li>
    <li><b>Broker context</b> - location, market, and investment-highlight narrative.</li>
  </ul>

  <h2>Why OM data is an <em>assertion</em>, not a fact</h2>
  <p>An OM is an <b>advertisement</b>: a broker's opinion of value that the seller agreed to before
     publication. The NOI may be in-place or pro-forma; the cap rate follows from a chosen price. So
     every figure is <b>an identified party's opinion as of a date</b> - not independently verified
     market truth. Any system that consumes OM data honestly must record <b>who</b> asserted it, that
     it is <b>unaltered</b>, and <b>as of when</b> - and must never claim the opinion is true.
     <b>Verified means provenance, not truth.</b></p>

  <h2>The problem: OM data is trapped in the PDF</h2>
  <p>Because the OM ships as a designed PDF, every downstream party - buyers, brokers, portals, lenders,
     and AI agents - re-extracts the same numbers by hand or with error-prone parsing. The work is
     repeated thousands of times and each copy can drift or be misread.</p>

  <h2>How openOM makes an offering memorandum machine-readable</h2>
  <p><a href="/">openOM</a> is an open (MIT) standard that embeds a <b>machine-readable,
     broker-asserted, hash-verified</b> data payload inside the OM PDF (via the same mechanism as
     Factur-X / PDF/A-3), and mirrors it as JSON-LD on the web. The data is extracted <b>once at the
     source</b> and consumed cheaply everywhere - with its provenance intact.</p>

  <h3>openOM vs. manual OM extraction</h3>
  <table>
    <thead><tr><th></th><th>Manual / AI re-extraction</th><th>openOM</th></tr></thead>
    <tbody>
      <tr><td>Where extraction happens</td><td>Every consumer, every time</td>
          <td>Once, at the source</td></tr>
      <tr><td>Provenance</td><td>Lost - who asserted what is unknown</td>
          <td>Recorded - assertedBy + assertedDate</td></tr>
      <tr><td>Integrity</td><td>Unverifiable</td><td>Hash-verified (RFC 8785 + SHA-256)</td></tr>
      <tr><td>AI reliability</td><td>Hallucination-prone re-parse</td>
          <td>Deterministic read of a verified payload</td></tr>
      <tr><td>Cost at scale</td><td>Repeated per document</td><td>Near-zero downstream</td></tr>
    </tbody>
  </table>

  <h2>Next steps</h2>
  <ul>
    <li><b>Brokers:</b> <a href="/docs/quickstart-broker.html">publish a verifiable OM →</a></li>
    <li><b>Portals / consumers:</b> <a href="/docs/quickstart-portal.html">read and trust openOM data →</a></li>
    <li><b>AI builders:</b> <a href="/docs/grounding-ai.html">ground your agent in verified OM facts →</a></li>
    <li><b>Verify one now:</b> <a href="/verify/">check an OM PDF in your browser →</a></li>
  </ul>
  <p><small>openOM is published by <a href="https://verveliolabs.com">Vervelio Labs</a>. The engine is
     deterministic and inference-free; every payload is an assertion, never a fact.</small></p>
"""
    faq = [
        (
            "What is an offering memorandum in commercial real estate?",
            "An offering memorandum (OM) is the marketing document a CRE broker prepares to offer a "
            "property for sale: it presents the property, the deal terms (asking price, cap rate, NOI), "
            "the tenancy, and the broker's opinion of value, usually as a designed PDF.",
        ),
        (
            "Is the data in an offering memorandum verified or true?",
            "No. An OM is an advertisement - a broker's opinion of value the seller agreed to before "
            "publication. Its figures are assertions as of a date, not independently verified market "
            "truth. openOM records who asserted the data, that it is unaltered, and as of when; "
            "verified means provenance, not truth.",
        ),
        (
            "What is the difference between an offering memorandum and a broker opinion of value?",
            "An offering memorandum is the full marketing package used to sell a property; the broker's "
            "opinion of value is the price/valuation view expressed within it. Every headline figure in "
            "an OM (price, cap rate, NOI) reflects that opinion.",
        ),
        (
            "How do you extract data from an offering memorandum PDF reliably?",
            "Instead of re-parsing the PDF per consumer, openOM embeds a machine-readable, "
            "broker-asserted, hash-verified payload in the OM itself (and mirrors it as JSON-LD), so any "
            "tool or AI agent reads the same verified data deterministically.",
        ),
    ]
    return _page(
        "What is an offering memorandum?",
        body,
        description=desc,
        canonical=canonical,
        jsonld=_jsonld(
            _article("What is an offering memorandum (OM)?", desc, canonical),
            _breadcrumb(canonical, "What is an offering memorandum?"),
            _faqpage(faq),
            {
                "@context": "https://schema.org",
                "@type": "DefinedTerm",
                "name": "Offering memorandum",
                "alternateName": ["OM", "offering memo", "CRE offering memorandum"],
                "description": desc,
                "url": SITE + canonical,
            },
        ),
        seo_title="What is an offering memorandum (OM)? - definition, contents & data",
    )


def docs_pages() -> dict[str, str]:
    """Return ``{relative_path_under_site: html}`` for the whole docs tree. Deterministic."""
    return {
        "verify/index.html": _verify_tool(),
        "docs/index.html": _docs_index(),
        "docs/what-is-an-offering-memorandum.html": _what_is_om(),
        "docs/grounding-ai.html": _grounding_ai(),
        "docs/quickstart-broker.html": _quickstart_broker(),
        "docs/quickstart-portal.html": _quickstart_portal(),
        "docs/quickstart-developer.html": _quickstart_developer(),
        "docs/schema-reference.html": _schema_reference(),
        "docs/codes.html": _codes_catalog(),
    }
