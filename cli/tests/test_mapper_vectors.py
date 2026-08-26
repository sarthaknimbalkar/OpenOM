"""Python side of the mapper differential corpus (the Buildout on-ramp anti-fork).

Locks the CLI Buildout mapper to its committed golden listing-derived output. The matching
extension/test/mapper-vectors.test.ts asserts the TS connector (buildoutListingToPayload) reproduces
the SAME listing-derived subtree - so the CLI bulk path and the extension author path can't fork the
embedded facts (they silently did at a .5 rounding tie before). Regenerate with
core/scripts/gen_mapper_corpus.py after any mapper change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openom_core.canonical import canonicalize

from openom_cli.buildout import listing_to_payload

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors" / "mapper"
_IDENTITY = ("assertedBy", "assertedDate", "@context", "@type", "specVersion", "meta")


def _lines(name: str) -> list[str]:
    return [ln for ln in (VECTORS / name).read_text(encoding="utf-8").splitlines() if ln]


def _derived(listing: dict[str, Any]) -> dict[str, Any]:
    p = listing_to_payload(
        listing, asserted_by={"broker": "B", "brokerage": "A", "license": "L"},
        asserted_date="2026-08-15", noi_type="in-place",
    )
    for k in _IDENTITY:
        p.pop(k, None)
    if isinstance(p.get("deal"), dict):
        p["deal"].pop("noiType", None)
        p["deal"].pop("noiAsOfDate", None)
    return p


def test_python_reproduces_committed_mapper_output() -> None:
    listings = _lines("listings.jsonl")
    expected = _lines("expected.jsonl")
    assert len(listings) == len(expected) >= 4
    for listing_line, expected_line in zip(listings, expected, strict=True):
        case = json.loads(listing_line)
        got = canonicalize(_derived(case["listing"])).decode("utf-8")  # JCS normal form
        assert got == expected_line, f"{case['name']}: {got} != {expected_line}"
