#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate the cross-implementation MAPPER corpus (the Buildout on-ramp anti-fork).

A Buildout listing is mapped to an openOM payload on TWO on-ramps: the CLI
(cli/openom_cli/buildout.py
listing_to_payload) and the extension connector (extension/src/author/extract/connectors/buildout.ts
buildoutListingToPayload). Their docstrings claim mutual parity, but nothing pinned it - and round 3
found they silently forked at a .5 rounding tie. This commits a set of listing inputs plus the
LISTING-DERIVED payload subtree (property/deal/lease, minus the caller-supplied identity) that
the Python mapper produces. Both on-ramps must reproduce it: cli/tests/test_mapper_vectors.py guards
Python, extension/test/mapper-vectors guards the TS connector.

Run after any mapper change:  python core/scripts/gen_mapper_corpus.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from openom_cli.buildout import listing_to_payload

from openom_core.canonical import canonicalize

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "spec" / "vectors" / "mapper"
FIXTURE = ROOT / "cli" / "tests" / "fixtures" / "buildout-listing-sample.json"

# Identity fields the CLI adds from flags but the TS connector leaves for the review gate; excluded
# from the parity contract, which is only the LISTING-DERIVED mapping.
_IDENTITY = ("assertedBy", "assertedDate", "@context", "@type", "specVersion", "meta")


def _derived(listing: dict[str, Any]) -> dict[str, Any]:
    p = listing_to_payload(
        listing, asserted_by={"broker": "B", "brokerage": "A", "license": "L"},
        asserted_date="2026-08-15", noi_type="in-place",
    )
    for k in _IDENTITY:
        p.pop(k, None)
    deal = p.get("deal")
    if isinstance(deal, dict):  # noiType/noiAsOfDate are identity, not listing-derived
        deal.pop("noiType", None)
        deal.pop("noiAsOfDate", None)
    return p


def _variants() -> list[tuple[str, dict[str, Any]]]:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out: list[tuple[str, dict[str, Any]]] = [("fixture", base)]

    multiunit = copy.deepcopy(base)  # pricePerUnit path
    multiunit["core"]["research_property_attributes.number_of_units"] = "8"
    out.append(("multiunit", multiunit))

    half_tie = copy.deepcopy(base)  # a .5 rounding tie in pricePerUnit (the round-3 fork)
    half_tie["financials"]["sale_price"] = 2500001
    half_tie["core"]["research_property_attributes.number_of_units"] = "2"
    out.append(("half-tie-priceperunit", half_tie))

    sparse = copy.deepcopy(base)  # missing financials/lease -> omitted, never guessed
    sparse["financials"] = {"sale_price": 900000}
    sparse["custom_fields"] = {}
    out.append(("sparse", sparse))

    gross = copy.deepcopy(base)  # lease-type + occupancy normalization
    gross["custom_fields"]["Lease type"] = "Modified Gross"
    gross["core"]["research_property_attributes.occupancy_pct"] = "92.5"
    out.append(("gross-lease", gross))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    listings: list[dict[str, Any]] = []
    expected: list[dict[str, Any]] = []
    for name, listing in _variants():
        listings.append({"name": name, "listing": listing})
        expected.append(_derived(listing))
    (OUT / "listings.jsonl").write_text(
        "".join(json.dumps(x, separators=(",", ":"), ensure_ascii=False) + "\n" for x in listings),
        encoding="utf-8",
    )
    # Compare via the RFC 8785 JCS canonical form (ECMAScript number model), not raw json.dumps -
    # so an integer-valued float serializes identically (42.0 -> "42") on both cores. JCS parity is
    # itself already pinned by the fuzz corpus, so it's the right normalizer for this comparison.
    (OUT / "expected.jsonl").write_text(
        "".join(canonicalize(x).decode("utf-8") + "\n" for x in expected),
        encoding="utf-8",
    )
    print(f"wrote {len(listings)} mapper vectors to {OUT}")


if __name__ == "__main__":
    main()
