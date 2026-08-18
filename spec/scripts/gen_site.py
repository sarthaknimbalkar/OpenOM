#!/usr/bin/env python3
"""Assemble the static hosting tree that serves openOM's pinned namespace URLs.

WHY: payloads carry ``"@context": [..., "https://verveliolabs.com/openom/ns/0.1"]``
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
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent
ROOT = SPEC.parent
SITE = ROOT / "site"

# The neutral steward's pinned base. Kept here (not spread across files) so a
# version/host change is one edit; the resolve-check reads it back from the specs.
BASE = "https://verveliolabs.com"
PREFIX = "openom"

# url-path (under BASE) -> (source file in spec/, content-type served).
# The url-path is also the on-disk path under site/ (a static host maps 1:1).
ARTIFACTS: dict[str, tuple[Path, str]] = {
    f"{PREFIX}/ns/0.1": (SPEC / "context" / "openom-0.1.jsonld", "application/ld+json"),
    f"{PREFIX}/spec/om-0.1.schema.json": (
        SPEC / "om-0.1.schema.json",
        "application/schema+json",
    ),
    f"{PREFIX}/spec/webhook-envelope-0.1.schema.json": (
        SPEC / "webhook-envelope-0.1.schema.json",
        "application/schema+json",
    ),
}


def _landing_html() -> str:
    """A minimal, dependency-free vocabulary landing served to browsers at /openom/.

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
  <h2>Resolvable artifacts</h2>
  <ul>
{links}
  </ul>
  <h2>Vocabulary (v0.1)</h2>
  <p>Terms in the <code>om:</code> namespace
     (<code>{BASE}/{PREFIX}/ns/0.1#</code>). schema.org terms are re-used where one
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


def generate() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    for path, (src, _ct) in ARTIFACTS.items():
        dest = SITE / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())  # byte-exact mirror; spec/ is the source
    (SITE / PREFIX / "index.html").write_text(_landing_html(), "utf-8", newline="\n")
    (SITE / "_headers").write_text(_headers_file(), "utf-8", newline="\n")
    # A bare deploy root should not 404; point it at the namespace landing.
    (SITE / "index.html").write_text(
        f'<!doctype html><meta http-equiv="refresh" content="0; url=/{PREFIX}/">\n',
        "utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    generate()
    print(f"wrote {SITE} ({len(ARTIFACTS)} artifacts + landing + _headers)")
