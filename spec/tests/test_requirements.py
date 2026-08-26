"""[Ma11] Every OM-* requirement ID cited anywhere in the committed sources MUST resolve to a
normative clause in spec/requirements.json - so a third party implementing openOM can look up every
ID the schema / codes.json / samples / reference implementation reference. Without this, those
back-references dangle and the standard cannot be independently implemented.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ = json.loads((ROOT / "spec" / "requirements.json").read_text(encoding="utf-8"))["requirements"]

# The committed sources that cite requirement IDs (NOT tests/planning/generated type files).
_SOURCE_GLOBS = [
    "spec/*.json",
    "spec/*.md",  # CHANGELOG etc.
    "spec/context/*",
    "spec/samples/*.json",
    "spec/vectors/**/*.md",  # the conformance-vector READMEs cite requirement IDs
    "core/src/**/*.py",
    "cli/src/**/*.py",
    "mcp/src/**/*.py",
    "js/src/**/*.ts",
    "js/widget/**/*.ts",
    "mcp-worker/src/**/*.ts",
    "process/**/*.md",  # the extraction playbook cites requirement IDs
    "extension/src/**/*.ts",  # the consumer/author surfaces cite trust/spec IDs
]
_ID_RE = re.compile(r"OM-[A-Z]+-\d+")
# Generated type files carry copied schema prose; the schema JSON is the authoritative citation.
_SKIP = {"js/src/schema.ts", "js/src/payload-types.ts"}


def _referenced_ids() -> set[str]:
    ids: set[str] = set()
    for pattern in _SOURCE_GLOBS:
        for f in glob.glob(str(ROOT / pattern), recursive=True):
            rel = Path(f).relative_to(ROOT).as_posix()
            if rel in _SKIP:
                continue
            ids |= set(_ID_RE.findall(Path(f).read_text(encoding="utf-8")))
    return ids


def test_every_referenced_requirement_id_resolves() -> None:
    referenced = _referenced_ids()
    dangling = sorted(i for i in referenced if i not in REQ)
    assert not dangling, (
        "requirement IDs cited in the code/spec have no clause in spec/requirements.json "
        f"(add them): {dangling}"
    )


def test_every_requirement_has_a_nonempty_clause_and_keyword() -> None:
    bad = sorted(
        i
        for i, v in REQ.items()
        if not v.get("clause", "").strip()
        or v.get("keyword") not in {"MUST", "MUST-NOT", "SHOULD", "MAY", "INFO", "UNKNOWN"}
    )
    assert not bad, f"requirements missing a clause or with an invalid keyword: {bad}"


def test_no_orphan_requirements() -> None:
    """A clause with no citation anywhere is dead weight; keep the registry honest (warn-free)."""
    referenced = _referenced_ids()
    orphans = sorted(i for i in REQ if i not in referenced)
    assert not orphans, f"requirements.json defines IDs nothing cites (remove or cite): {orphans}"
