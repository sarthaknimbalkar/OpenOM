#!/usr/bin/env python3
"""Assemble the static hosting tree that serves openOM's pinned namespace URLs.

WHY: payloads carry ``"@context": [..., "https://openom.app/ns/0.1"]``
and the schemas pin absolute ``$id`` URLs. A JSON-LD processor dereferences that
context URL and a ``$ref``/``$id`` resolver fetches the schemas — so if those URLs
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
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>openOM namespace 0.1</title>
  <style>
    body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 44rem; margin: 3rem auto;
            padding: 0 1rem; color: #111; }}
    code {{ background: #f4f4f5; padding: 0.1em 0.35em; border-radius: 4px; }}
    small {{ color: #666; }}
    h1 {{ margin-bottom: 0.2rem; }}
  </style>
</head>
<body>
  <h1>openOM</h1>
  <p>Machine-readable, broker-asserted data for commercial-real-estate offering
     memoranda. Published by <a href="https://verveliolabs.com">Vervelio Labs</a>.
     Spec + toolchain: <a href="https://github.com/sarthaknimbalkar/OpenOM">GitHub</a>.</p>
  <p><strong>New here? <a href="/docs/">Read the docs</a></strong> — per-persona
     quick-starts, the field reference, and the validation-code catalog.</p>
  <h2>Resolvable artifacts</h2>
  <ul>
{links}
  </ul>
  <h2>Vocabulary (v0.1)</h2>
  <p>Terms in the <code>om:</code> namespace
     (<code>{BASE}/ns/0.1#</code>). schema.org terms are re-used where one
     exists; see the JSON-LD context for the full mapping.</p>
  <ul>
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
    """Apache/cPanel ``.htaccess`` — the same content-type + CORS rules for hosts that use Apache
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
    (SITE / "index.html").write_text(_landing_html(), "utf-8", newline="\n")  # landing = site root
    (SITE / "_headers").write_text(_headers_file(), "utf-8", newline="\n")
    (SITE / ".htaccess").write_text(_htaccess_file(), "utf-8", newline="\n")  # Apache/GoDaddy


if __name__ == "__main__":
    generate()
    print(f"wrote {SITE} ({len(ARTIFACTS)} artifacts + landing + _headers + .htaccess)")
