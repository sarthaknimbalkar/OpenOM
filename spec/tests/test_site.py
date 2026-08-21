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


@pytest.mark.skipif(
    not os.environ.get("OPENOM_SITE_BASE"),
    reason="live resolve-check; set OPENOM_SITE_BASE to the deployed origin",
)
def test_live_urls_resolve() -> None:  # pragma: no cover - manual post-deploy only
    import urllib.request

    base = os.environ["OPENOM_SITE_BASE"].rstrip("/")
    gen = _load_gen()
    for path, (src, _ct) in gen.ARTIFACTS.items():
        with urllib.request.urlopen(f"{base}/{path}", timeout=15) as r:  # noqa: S310
            body = r.read()
        assert body == src.read_bytes(), f"{base}/{path} differs from {src}"
        assert json.loads(body) is not None
