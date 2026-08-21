#!/usr/bin/env python3
"""Assemble the static hosting tree that serves openOM's pinned namespace URLs.

WHY: payloads carry ``"@context": [..., "https://openom.app/ns/0.1"]``
and the schemas pin absolute ``$id`` URLs. A JSON-LD processor dereferences that
context URL and a ``$ref``/``$id`` resolver fetches the schemas - so if those URLs
do not serve the *exact committed bytes* with the right content-type and CORS, the
web half of the standard is inert. This script mirrors the ``spec/`` artifacts into
a deploy root (``site/``) at the exact paths the URLs pin, keeping ``spec/`` the
single source of truth. Deterministic: same inputs -> byte-identical tree, so CI
can regenerate and assert no drift.

Run: ``python spec/scripts/gen_site.py`` (writes ``site/``).
The mirror is verified byte-for-byte by ``spec/tests/test_site.py``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_docs import docs_pages  # noqa: E402  (local sibling module)

SPEC = Path(__file__).resolve().parent.parent
ROOT = SPEC.parent
SITE = ROOT / "site"

# The neutral steward's pinned base. Kept here (not spread across files) so a
# version/host change is one edit; the resolve-check reads it back from the specs.
BASE = "https://openom.app"

# url-path (under BASE) -> (source file in spec/, content-type served). The domain is dedicated to
# openOM, so paths are bare (no / prefix): the namespace is BASE/ns/0.1 etc. The url-path is
# also the on-disk path under site/ (a static host maps 1:1).
ARTIFACTS: dict[str, tuple[Path, str]] = {
    "ns/0.1": (SPEC / "context" / "openom-0.1.jsonld", "application/ld+json"),
    "spec/om-0.1.schema.json": (SPEC / "om-0.1.schema.json", "application/schema+json"),
    "spec/webhook-envelope-0.1.schema.json": (
        SPEC / "webhook-envelope-0.1.schema.json",
        "application/schema+json",
    ),
}


def _landing_html() -> str:
    """A minimal, dependency-free vocabulary landing served to browsers at /.

    Machines get JSON; humans following the namespace URL get orientation + links.
    """
    ctx = json.loads((SPEC / "context" / "openom-0.1.jsonld").read_text("utf-8"))
    terms = sorted(k for k in ctx["@context"] if not k.startswith("@") and k[:1].islower())
    rows = "\n".join(
        f"      <li><code>om:{t}</code></li>" for t in terms if ":" not in t
    )
    links = "\n".join(
        f'      <li><a href="/{p}">/{p}</a> <small>({ct})</small></li>'
        for p, (_src, ct) in ARTIFACTS.items()
    )
    desc = (
        "openOM is an open standard that embeds machine-readable, broker-asserted, "
        "hash-verified data inside commercial real estate offering memorandum PDFs, mirrored "
        "as JSON-LD on the web. Extract once at the source; consume cheaply everywhere."
    )
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Vervelio Labs",
        "url": "https://verveliolabs.com",
        "brand": {"@type": "Brand", "name": "openOM"},
    }
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "openOM",
        "url": BASE + "/",
        "description": desc,
        "publisher": {"@type": "Organization", "name": "Vervelio Labs"},
    }
    software = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "openOM",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Cross-platform",
        "url": BASE + "/",
        "description": desc,
        "license": "https://opensource.org/licenses/MIT",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "publisher": {"@type": "Organization", "name": "Vervelio Labs"},
    }
    faq = [
        (
            "What is openOM?",
            "openOM is an open (MIT) standard and toolchain that embeds machine-readable, "
            "broker-asserted, hash-verified data inside commercial real estate offering memorandum "
            "PDFs, and mirrors the same payload as JSON-LD on the web. Data is extracted once at the "
            "source and consumed cheaply everywhere.",
        ),
        (
            "Is openOM data verified to be true?",
            "No. An offering memorandum is an advertisement - a broker's opinion of value. openOM "
            "records who asserted the data, that it is unaltered, and as of when. Verified means "
            "provenance, not truth; openOM never claims the opinion is correct.",
        ),
        (
            "Is openOM free?",
            "Yes. The standard, schema, and reference toolchain are free and open source under the "
            "MIT license (the spec under CC-BY-4.0). Everything deterministic is self-hostable at no "
            "cost.",
        ),
        (
            "How do I read openOM data with an AI agent?",
            "Point your MCP client at an openOM server and read the broker-asserted, hash-verified "
            "payload via om_read - a deterministic ground truth instead of hallucination-prone PDF "
            "extraction.",
        ),
        (
            "Does openOM use AI or inference?",
            "The engine, server, and consumer tooling contain zero inference - they are fully "
            "deterministic and testable. Optional AI assists only the authoring step, on-device or "
            "client-side, and a human reviews every assertion before it is embedded.",
        ),
    ]
    faqpage = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }
    vocab_terms = [t for t in terms if ":" not in t]
    termset = {
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "name": "openOM vocabulary 0.1",
        "url": BASE + "/ns/0.1",
        "description": "The openOM 0.1 vocabulary for commercial real estate offering-memorandum data.",
        "hasDefinedTerm": [
            {
                "@type": "DefinedTerm",
                "name": f"om:{t}",
                "inDefinedTermSet": BASE + "/ns/0.1",
                "url": f"{BASE}/ns/0.1#{t}",
            }
            for t in vocab_terms
        ],
    }
    jsonld = "\n".join(
        f'  <script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>'
        for o in (org, website, software, faqpage, termset)
    )
    faq_html = "\n".join(
        f"    <details><summary>{q}</summary>\n    <p>{a}</p></details>" for q, a in faq
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>openOM - verifiable data for CRE offering memoranda</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{BASE}/" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large" />
  <meta name="author" content="Vervelio Labs" />
  <meta name="theme-color" content="#0b1021" />
  <link rel="alternate" type="application/ld+json" href="{BASE}/ns/0.1" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="openOM" />
  <meta property="og:title" content="openOM - verifiable data for CRE offering memoranda" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{BASE}/" />
  <meta property="og:image" content="{BASE}/og.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="openOM - verifiable data for CRE offering memoranda" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{BASE}/og.png" />
{jsonld}
  <style>
    body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 52rem; margin: 0 auto;
            padding: 0 1rem 4rem; color: #111; }}
    a {{ color: #065f46; }}
    code {{ background: #f4f4f5; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.9em; }}
    small {{ color: #666; }}
    header.hero {{ background: #0b1021; color: #e6edf3; margin: 0 -100vw 2rem; padding: 3.5rem 100vw 3rem; }}
    header.hero h1 {{ font-size: 3rem; margin: 0 0 0.4rem; }}
    header.hero h1 .om {{ color: #10b981; }}
    header.hero p {{ font-size: 1.25rem; max-width: 40rem; margin: 0.4rem 0; }}
    header.hero .sub {{ color: #94a3b8; font-size: 1rem; }}
    .cta {{ display: inline-block; margin-top: 1rem; background: #10b981; color: #05261b;
            font-weight: 600; padding: 0.6rem 1.1rem; border-radius: 8px; text-decoration: none; }}
    .cta.ghost {{ background: transparent; color: #e6edf3; border: 1px solid #334155; margin-left: 0.5rem; }}
    h2 {{ margin-top: 2.5rem; }}
    .cards {{ display: grid; gap: 1rem; grid-template-columns: 1fr; }}
    @media (min-width: 40rem) {{ .cards {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 1rem 1.1rem; }}
    .card h3 {{ margin: 0 0 0.3rem; }}
    details {{ border-bottom: 1px solid #e5e7eb; padding: 0.6rem 0; }}
    summary {{ font-weight: 600; cursor: pointer; }}
    details p {{ margin: 0.5rem 0 0; }}
    .cols {{ columns: 2; }}
  </style>
</head>
<body>
  <header class="hero">
    <h1>open<span class="om">OM</span></h1>
    <p>Verifiable, machine-readable data for commercial real estate offering memoranda.</p>
    <p class="sub">An open standard that embeds broker-asserted, hash-verified data inside the OM
       PDF - extracted once at the source, consumed cheaply everywhere.</p>
    <a class="cta" href="/docs/">Read the docs</a>
    <a class="cta ghost" href="/verify/">Verify a PDF</a>
  </header>

  <p><b>openOM</b> is an open (MIT) standard and toolchain that embeds machine-readable,
     broker-asserted, hash-verified data inside commercial real estate (CRE) offering memorandum
     (OM) PDFs, and mirrors the same payload as JSON-LD on the web. One extraction at the source
     replaces the same work repeated by every buyer, broker, portal, lender, and AI agent
     downstream. Published by <a href="https://verveliolabs.com">Vervelio Labs</a>;
     source on <a href="https://github.com/sarthaknimbalkar/OpenOM">GitHub</a>.</p>

  <p><b>Verified means provenance, not truth.</b> An OM is an advertisement - a broker's opinion of
     value the seller agreed to before publication. openOM records <i>who</i> asserted the data,
     that it is <i>unaltered</i>, and <i>as of when</i>; it never claims the opinion is true. The
     engine is deterministic and inference-free.</p>

  <h2>Who it's for</h2>
  <div class="cards">
    <div class="card"><h3>Brokers &amp; authors</h3>
      <p>Publish an OM that carries structured, verifiable data - visually identical output.</p>
      <p><a href="/docs/quickstart-broker.html">Broker quick-start →</a></p></div>
    <div class="card"><h3>Portals &amp; consumers</h3>
      <p>Read and trust openOM data on OMs you host or receive, with an honest trust badge.</p>
      <p><a href="/docs/quickstart-portal.html">Portal quick-start →</a></p></div>
    <div class="card"><h3>Developers</h3>
      <p>Build against the standard: JSON Schema, JSON-LD context, Python + TypeScript.</p>
      <p><a href="/docs/quickstart-developer.html">Developer quick-start →</a></p></div>
    <div class="card"><h3>AI builders</h3>
      <p>Ground your CRE agent in verified facts via MCP instead of re-parsing PDFs.</p>
      <p><a href="/docs/grounding-ai.html">Grounding AI agents →</a></p></div>
  </div>

  <h2>New to offering memoranda?</h2>
  <p>Start with <a href="/docs/what-is-an-offering-memorandum.html">What is an offering
     memorandum?</a> - the definition, what an OM contains, and why its data is an assertion.</p>

  <h2>Frequently asked questions</h2>
{faq_html}

  <h2>Resolvable artifacts</h2>
  <ul>
{links}
  </ul>

  <h2>Vocabulary (v0.1)</h2>
  <p>Terms in the <code>om:</code> namespace
     (<code>{BASE}/ns/0.1#</code>). schema.org terms are re-used where one
     exists; see the <a href="/ns/0.1">JSON-LD context</a> for the full mapping.</p>
  <ul class="cols">
{rows}
  </ul>
</body>
</html>
"""


def _headers_file() -> str:
    """Cloudflare Pages ``_headers``: content-type + open CORS per artifact.

    JSON-LD/schema fetches are cross-origin from any consumer, so ``*`` CORS is
    required; the extensionless ``ns/0.1`` needs an explicit content-type a static
    host would otherwise serve as octet-stream.
    """
    blocks = ["/*\n  Access-Control-Allow-Origin: *\n"]
    for path, (_src, ct) in ARTIFACTS.items():
        blocks.append(f"/{path}\n  Content-Type: {ct}\n  Cache-Control: public, max-age=3600\n")
    return "\n".join(blocks)


def _htaccess_file() -> str:
    """Apache/cPanel ``.htaccess`` - the same content-type + CORS rules for hosts that use Apache
    (e.g. GoDaddy Linux hosting) instead of a ``_headers``-style static host (Cloudflare/Netlify).

    ``<FilesMatch>`` is valid in .htaccess (unlike ``<Location>``): the extensionless JSON-LD
    context file is named ``0.1`` and the schemas end ``.schema.json``, so basename matching covers
    the tree from one root file. ``ForceType`` sets the type; ``mod_headers`` adds CORS.
    """
    return (
        "# openOM namespace headers for Apache / cPanel hosts (e.g. GoDaddy Linux hosting).\n"
        "# Cloudflare Pages / Netlify use _headers instead; both are generated so the site is\n"
        "# host-portable. Keep in sync with _headers via gen_site.py.\n"
        "<IfModule mod_headers.c>\n"
        '  Header set Access-Control-Allow-Origin "*"\n'
        '  Header set Cache-Control "public, max-age=3600"\n'
        "</IfModule>\n"
        '<FilesMatch "^0\\.1$">\n'
        "  ForceType application/ld+json\n"
        "</FilesMatch>\n"
        '<FilesMatch "\\.schema\\.json$">\n'
        "  ForceType application/schema+json\n"
        "</FilesMatch>\n"
    )


def _page_url(rel: str) -> str:
    """Map a generated page path to its clean canonical URL (index.html -> dir; .html dropped)."""
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel.removesuffix(".html")


def _all_urls() -> list[str]:
    """Every crawlable openOM URL, canonical form, deterministic order. Landing first, then pages,
    then the machine artifacts (namespace + schemas) so AI/answer engines can find them too."""
    pages = sorted(_page_url(r) for r in docs_pages())
    arts = [f"/{p}" for p in ARTIFACTS]
    return ["/", *pages, *arts]


def _robots_file() -> str:
    """robots.txt: open the whole site to every crawler, INCLUDING the AI/answer engines
    (AEO/GEO/AIO distribution). Explicit allows silence any doubt about GPTBot/ClaudeBot/etc.,
    and point everyone at the sitemap."""
    ai_bots = [
        "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web", "anthropic-ai",
        "PerplexityBot", "Perplexity-User", "Google-Extended", "Googlebot", "Bingbot",
        "Applebot", "Applebot-Extended", "CCBot", "Amazonbot", "cohere-ai", "Meta-ExternalAgent",
        "DuckDuckBot", "YandexBot",
    ]
    blocks = "\n\n".join(f"User-agent: {b}\nAllow: /" for b in ["*", *ai_bots])
    return f"{blocks}\n\nSitemap: {BASE}/sitemap.xml\n"


def _sitemap_file() -> str:
    """sitemap.xml over every canonical URL. No <lastmod> - it would be nondeterministic and trip
    the drift gate; search engines treat its absence fine."""
    urls = "\n".join(f"  <url><loc>{BASE}{u}</loc></url>" for u in _all_urls())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def _llms_file() -> str:
    """llms.txt (llmstxt.org): a curated, plain-text map for LLMs/answer engines - what openOM is,
    in one honest paragraph, then the canonical links worth reading. This is the AIO/GEO on-ramp."""
    lines = [
        "# openOM",
        "",
        "> An open (MIT) standard and toolchain that embeds machine-readable, broker-asserted,",
        "> hash-verified data inside commercial real estate (CRE) offering memorandum (OM) PDFs,",
        "> and mirrors the same payload as JSON-LD on the web. Extract once at the source; consume",
        "> cheaply everywhere. Published by Vervelio Labs.",
        "",
        "An offering memorandum is an advertisement - a broker's opinion of value, agreed to by the",
        "seller before publication. openOM records who asserted the data, that it is unaltered, and",
        "as of when. Verified means provenance (who / unaltered / as-of-when), NOT that the opinion",
        "is true. The engine is deterministic and inference-free; every payload is an identified",
        "party's opinion as of a date - assertions, never facts.",
        "",
        "## Docs",
        "",
        f"- [Documentation home]({BASE}/docs/): per-persona quick-starts and reference.",
        f"- [What is an offering memorandum?]({BASE}/docs/what-is-an-offering-memorandum): the"
        " definition, an OM's contents, and why its data is an assertion not a fact.",
        f"- [Grounding AI agents in openOM]({BASE}/docs/grounding-ai): read verified OM facts via MCP"
        " instead of hallucination-prone PDF extraction.",
        f"- [Broker quick-start]({BASE}/docs/quickstart-broker): publish an OM carrying verifiable data.",
        f"- [Portal quick-start]({BASE}/docs/quickstart-portal): read and trust openOM data.",
        f"- [Developer quick-start]({BASE}/docs/quickstart-developer): build against the standard.",
        f"- [Field reference]({BASE}/docs/schema-reference): every payload field, from the schema.",
        f"- [Validation code catalog]({BASE}/docs/codes): every error/warning/info code.",
        f"- [Verify a PDF]({BASE}/verify/): check an openOM PDF in the browser.",
        "",
        "## Machine artifacts",
        "",
        f"- [JSON-LD context]({BASE}/ns/0.1): the openOM 0.1 vocabulary.",
        f"- [JSON Schema]({BASE}/spec/om-0.1.schema.json): the openOM 0.1 payload schema.",
        f"- [Webhook envelope schema]({BASE}/spec/webhook-envelope-0.1.schema.json).",
        f"- [Source and toolchain](https://github.com/sarthaknimbalkar/OpenOM): Python + TypeScript,"
        " MIT.",
        "",
    ]
    return "\n".join(lines)


def _not_found_html() -> str:
    """Branded 404 (Cloudflare Pages serves /404.html for unknown paths). noindex - it must never
    rank - but it keeps a lost visitor oriented with links back into the site."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Not found - openOM</title>
  <meta name="robots" content="noindex, follow" />
  <meta name="theme-color" content="#0b1021" />
  <style>
    body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 40rem; margin: 4rem auto;
            padding: 0 1rem; color: #111; }}
    a {{ color: #065f46; }}
    h1 {{ font-size: 2.5rem; margin-bottom: 0.2rem; }}
  </style>
</head>
<body>
  <h1>404</h1>
  <p>That page isn't here. Try:</p>
  <ul>
    <li><a href="/">openOM home</a></li>
    <li><a href="/docs/">Documentation</a></li>
    <li><a href="/docs/what-is-an-offering-memorandum">What is an offering memorandum?</a></li>
    <li><a href="/verify/">Verify a PDF</a></li>
  </ul>
</body>
</html>
"""


def generate() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    for path, (src, _ct) in ARTIFACTS.items():
        dest = SITE / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())  # byte-exact mirror; spec/ is the source
    for rel, page_html in docs_pages().items():
        dest = SITE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page_html, "utf-8", newline="\n")
    (SITE / "og.png").write_bytes((SPEC / "assets" / "og.png").read_bytes())  # social share card
    (SITE / "index.html").write_text(_landing_html(), "utf-8", newline="\n")  # landing = site root
    (SITE / "404.html").write_text(_not_found_html(), "utf-8", newline="\n")  # Pages custom 404
    (SITE / "_headers").write_text(_headers_file(), "utf-8", newline="\n")
    (SITE / ".htaccess").write_text(_htaccess_file(), "utf-8", newline="\n")  # Apache/GoDaddy
    (SITE / "robots.txt").write_text(_robots_file(), "utf-8", newline="\n")  # AEO/GEO/AIO crawlers
    (SITE / "sitemap.xml").write_text(_sitemap_file(), "utf-8", newline="\n")
    (SITE / "llms.txt").write_text(_llms_file(), "utf-8", newline="\n")  # llmstxt.org AIO on-ramp


if __name__ == "__main__":
    generate()
    print(f"wrote {SITE} ({len(ARTIFACTS)} artifacts + landing + _headers + .htaccess)")
