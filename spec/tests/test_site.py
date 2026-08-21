"""[#139] Every pinned namespace/schema URL must serve the exact committed bytes.

Two guarantees, both deterministic (no network in CI):

1. **Drift** - the committed ``site/`` deploy tree is exactly what ``gen_site.py``
   produces from ``spec/``. If someone edits a schema but not the mirror, this fails,
   so the hosted artifact can never silently diverge from the source of truth.

2. **Resolve-check** - every absolute ``$id`` and ``@context`` URL under the pinned
   base that appears anywhere in ``spec/`` maps to a file in ``site/`` at the
   mirrored path, byte-identical to the artifact it names. A schema whose ``$id`` has
   no served file (or serves stale bytes) is exactly the "unresolvable namespace"
   the standard's web half dies on.

An optional live mode (``OPENOM_SITE_BASE=https://…`` set) fetches each URL and
diffs - for post-deploy verification, run manually; never in CI.
"""

from __future__ import annotations

import filecmp
import importlib.util
import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
SITE = ROOT / "site"


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "gen_site", SPEC / "scripts" / "gen_site.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dir_equal(a: Path, b: Path) -> list[str]:
    """Return a list of drift descriptions ([] == identical trees)."""
    cmp = filecmp.dircmp(a, b)
    problems = [f"only in {a}: {cmp.left_only}"] if cmp.left_only else []
    if cmp.right_only:
        problems.append(f"only in {b}: {cmp.right_only}")
    if cmp.diff_files:
        problems.append(f"differ: {cmp.diff_files}")
    for sub in cmp.common_dirs:
        problems += _dir_equal(a / sub, b / sub)
    return problems


def test_site_matches_generator(tmp_path: Path) -> None:
    gen = _load_gen()
    staging = tmp_path / "site"
    gen.SITE = staging  # redirect output; keep spec sources intact
    gen.generate()
    assert SITE.exists(), "site/ is not committed - run: python spec/scripts/gen_site.py"
    drift = _dir_equal(SITE, staging)
    assert not drift, "site/ is stale; run gen_site.py:\n" + "\n".join(drift)


def _pinned_urls() -> dict[str, Path]:
    """Every absolute openOM URL referenced in spec/ -> its authoritative source file."""
    gen = _load_gen()
    base = f"{gen.BASE}/"
    # url (full) -> source spec file, from the generator's own manifest.
    manifest = {f"{gen.BASE}/{p}": src for p, (src, _ct) in gen.ARTIFACTS.items()}
    # Scan spec/*.json + context for any URL under BASE; each MUST be in the manifest,
    # so a newly-pinned URL that nobody hosted trips this immediately.
    seen: set[str] = set()
    for f in list(SPEC.glob("*.json")) + list((SPEC / "context").glob("*.jsonld")):
        for m in re.findall(rf"{re.escape(base)}[^\"#\s,)]+", f.read_text("utf-8")):
            seen.add(m)
    unhosted = seen - set(manifest)
    assert not unhosted, f"pinned URLs with no hosted artifact (add to gen_site.py): {unhosted}"
    return manifest


def test_every_pinned_url_resolves_to_committed_bytes() -> None:
    for url, src in _pinned_urls().items():
        rel = url.removeprefix(_load_gen().BASE + "/")
        served = SITE / rel
        assert served.exists(), f"{url} -> missing {served}"
        assert served.read_bytes() == src.read_bytes(), f"{url} serves stale bytes vs {src}"


def _live_get(url: str) -> tuple[int, str, bytes]:  # pragma: no cover - manual post-deploy only
    """GET a live URL with a browser-like UA (the CDN 403s the default urllib UA). Returns
    (status, content-type, body); status 0 on transport failure."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 openom-livecheck"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception:
        return 0, "", b""


@pytest.mark.skipif(
    not os.environ.get("OPENOM_SITE_BASE"),
    reason="live resolve-check; set OPENOM_SITE_BASE to the deployed origin",
)
def test_live_urls_resolve() -> None:  # pragma: no cover - manual post-deploy only
    base = os.environ["OPENOM_SITE_BASE"].rstrip("/")
    gen = _load_gen()
    for path, (src, _ct) in gen.ARTIFACTS.items():
        status, _ct2, body = _live_get(f"{base}/{path}")
        assert status == 200, f"{base}/{path} -> {status}"
        assert body == src.read_bytes(), f"{base}/{path} differs from {src}"
        assert json.loads(body) is not None


@pytest.mark.skipif(
    not os.environ.get("OPENOM_SITE_BASE"),
    reason="live post-deploy smoke; set OPENOM_SITE_BASE to the deployed origin",
)
def test_live_site_smoke() -> None:  # pragma: no cover - manual post-deploy only
    """Post-deploy: every generated HTML page + every non-artifact asset the pages reference must
    serve 200 with the right content-type on the LIVE origin, and no internal link may 404. This is
    the guard for the 'passes locally, 404s live' class (e.g. an un-deployed widget bundle)."""
    import re

    base = os.environ["OPENOM_SITE_BASE"].rstrip("/")

    # 1. Every generated HTML page resolves (clean URL) as text/html.
    for rel in _load_gen_docs_pages():
        url = base + _clean_url(rel)
        status, ct, _b = _live_get(url)
        assert status == 200 and "text/html" in ct, f"{url} -> {status} {ct}"

    # 2. Every non-artifact asset the site depends on serves 200 with the expected content-type.
    assets = {
        "/favicon.ico": "image",
        "/og.png": "image/png",
        "/robots.txt": "text/plain",
        "/sitemap.xml": "xml",
        "/llms.txt": "text/plain",
        "/widget/openom-badge.js": "javascript",  # the bug that shipped: 404 broke /verify/
    }
    for path, ct_needle in assets.items():
        status, ct, _b = _live_get(base + path)
        assert status == 200, f"{base}{path} -> {status}"
        assert ct_needle in ct, f"{base}{path} content-type {ct!r} lacks {ct_needle!r}"

    # 3. No internal link on the landing or docs index 404s.
    seen: set[str] = set()
    for start in ("/", "/docs/"):
        _s, _ct, body = _live_get(base + start)
        for href in re.findall(r'href="(/[^"#]*)"', body.decode("utf-8", "replace")):
            if href in seen:
                continue
            seen.add(href)
            status, _c, _b = _live_get(base + href)
            assert status == 200, f"internal link {base}{href} -> {status}"


def _clean_url(rel: str) -> str:
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel.removesuffix(".html")


def _load_gen_docs_pages() -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "gen_docs", SPEC / "scripts" / "gen_docs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.docs_pages().keys())
