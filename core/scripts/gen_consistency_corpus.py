#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate the cross-language CONSISTENCY differential corpus (the warning/info-tier anti-fork).

The ~30 consistency rules in validate.py and validate.ts only *coincidentally* agree today - nothing
forces them to. This produces a DETERMINISTIC, boundary-weighted corpus of schema-valid payloads and
the exact set of warning+info findings the Python core emits for each (code + path, sorted). Both
cores validate the SAME corpus and MUST reproduce the SAME finding set: test_consistency_vectors.py
guards Python against its own committed corpus, and js/test/consistency-vectors.test.ts is the
anti-fork assertion (a rule that fires in one impl but not the other fails there).

Only the DEFAULT validate path is exercised (no caller as_of), so the corpus is a pure function of
the payload - W032 (needs a processing date) is intentionally out of scope. Prose messages and raw
expected/actual floats are NOT part of the contract; the machine-actionable {code, path} pair is.

The generator is seeded (no Date/urandom), so re-running is a no-op - a diff means a finding moved.
Run after any consistency-rule change:  python core/scripts/gen_consistency_corpus.py
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openom_core.schema import load_schema
from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "spec" / "vectors" / "consistency"
SKELETON = ROOT / "spec" / "samples" / "valid-stnl.json"
SEED = 20260825  # fixed seed -> reproducible corpus
COUNT = 300  # error-free payloads to collect

_SCHEMA = load_schema()


def _base() -> dict[str, Any]:
    return json.loads(SKELETON.read_text(encoding="utf-8"))


# --- mutators: each nudges the skeleton toward one or a few rule boundaries. A mutator returns None
#     to signal "not applied this time" so the seeded subset stays varied. Deltas straddle the
#     tolerance so the corpus exercises both sides of every comparison operator (where round()/float
#     divergence bites). All mutations keep the payload SCHEMA-VALID (else the error tier fires and
#     the vector is dropped below). ---

Delta = Callable[[dict[str, Any], random.Random], None]


def _off_or_on(rng: random.Random, tol: float, scale: float) -> float:
    """A signed nudge either just inside or just outside `tol` (in `scale` units)."""
    inside = rng.random() < 0.4
    mag = tol * (0.5 if inside else rng.uniform(1.2, 4.0))
    return (mag if rng.random() < 0.5 else -mag) * scale


def m_caprate(p: dict[str, Any], rng: random.Random) -> None:
    deal = p["deal"]
    if "noi" not in deal or "askingPrice" not in deal:
        return  # a prior mutator removed an input this one needs
    implied = deal["noi"] / deal["askingPrice"]
    deal["capRate"] = round(max(1e-4, implied + _off_or_on(rng, 0.005, 1.0)), 6)  # W010 / W013


def m_caprate_band(p: dict[str, Any], rng: random.Random) -> None:
    p["deal"]["capRate"] = rng.choice([0.005, 0.015, 0.019, 0.25, 0.5])  # W013 (band [0.02, 0.20])


def m_priceperSF(p: dict[str, Any], rng: random.Random) -> None:
    if "askingPrice" not in p["deal"]:
        return
    implied = p["deal"]["askingPrice"] / p["property"]["buildingSF"]
    p["deal"]["pricePerSF"] = round(implied * (1 + _off_or_on(rng, 0.01, 1.0)), 2)  # W011


def m_noi_nonpositive(p: dict[str, Any], rng: random.Random) -> None:
    p["deal"]["noi"] = rng.choice([0, -5000, -1])  # W014 (noi has no schema minimum)


def m_proforma(p: dict[str, Any], rng: random.Random) -> None:
    p["deal"]["noiType"] = "pro-forma"
    if rng.random() < 0.6:
        # W012 fires when a pro-forma NOI has no noiAsOfDate. The schema requires noiAsOfDate ONLY
        # when noi is present, so drop noi too - else it's a schema error and the vector drops.
        p["deal"].pop("noiAsOfDate", None)
        p["deal"].pop("noi", None)


def m_i003_skipped_crosscheck(p: dict[str, Any], rng: random.Random) -> None:
    # OMI-I003: a cross-check skipped for absent inputs. capRate present, noi/askingPrice absent
    # -> the NOI/price cross-check (W010) is skipped and noted as info.
    p["deal"]["capRate"] = 0.06
    p["deal"].pop("noi", None)
    p["deal"].pop("noiType", None)  # noiType/noiAsOfDate are only required alongside noi
    p["deal"].pop("noiAsOfDate", None)
    if rng.random() < 0.5:
        p["deal"].pop("askingPrice", None)


def m_currency_nonus(p: dict[str, Any], rng: random.Random) -> None:
    p.pop("currency", None)  # I001 always; W061 when country is non-US
    p["property"]["address"]["addressCountry"] = rng.choice(["CA", "GB", "US", "MX"])


def m_net_lease_landlord(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["leaseTypeAsserted"] = rng.choice(["NN", "NNN", "absolute-net"])
    resp = p["lease"]["landlordResponsibilities"]
    for k in ("taxes", "insurance", "cam"):
        resp[k] = rng.random() < 0.5  # W040 / W041
    for k in ("roof", "structure", "parking", "hvac"):
        resp[k] = rng.random() < 0.5  # W041 absolute-net structural


def m_gross_lease(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["leaseTypeAsserted"] = rng.choice(["gross", "modified-gross"])
    resp = p["lease"]["landlordResponsibilities"]
    for k in resp:
        resp[k] = False  # W041 (gross but landlord bears nothing)


def m_rent_year1_vs_noi(p: dict[str, Any], rng: random.Random) -> None:
    if "noi" not in p["deal"]:
        return
    p["deal"]["noiType"] = "in-place"
    noi = p["deal"]["noi"]
    row = p["lease"]["rentSchedule"][0]
    row["annualRent"] = round(noi * (1 + _off_or_on(rng, 0.01, 1.0)))  # W020


def m_rentpsf(p: dict[str, Any], rng: random.Random) -> None:
    row = p["lease"]["rentSchedule"][0]
    implied = row["annualRent"] / p["property"]["buildingSF"]
    row["rentPSF"] = round(implied * (1 + _off_or_on(rng, 0.01, 1.0)), 2)  # W024


def m_monthly(p: dict[str, Any], rng: random.Random) -> None:
    row = p["lease"]["rentSchedule"][0]
    row["monthlyRent"] = round(row["annualRent"] / 12 * (1 + _off_or_on(rng, 0.01, 1.0)), 2)  # W025


def m_source_verified(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["rentSchedule"][rng.randint(0, 1)]["source"] = "verified"  # W060


def m_source_absent(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["rentSchedule"][0].pop("source", None)  # I002


def m_escalation(p: dict[str, Any], rng: random.Random) -> None:
    sched = p["lease"]["rentSchedule"]
    step = sched[1]["annualRent"] / sched[0]["annualRent"] - 1
    sched[1]["escalationFromPrior"] = round(step + _off_or_on(rng, 0.005, 1.0), 4)  # W023


def m_period_gap_overlap(p: dict[str, Any], rng: random.Random) -> None:
    sched = p["lease"]["rentSchedule"]
    if rng.random() < 0.5:
        sched[1]["periodStart"] = "2029-04-15"  # W022 overlap (before prior periodEnd)
    else:
        sched[1]["periodStart"] = "2029-06-15"  # W021 gap (> 1 day after prior periodEnd)


def m_period_outside_term(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["rentSchedule"][0]["periodStart"] = "2018-01-01"  # W026 (before commencement)


def m_term_months(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["termMonths"] = rng.choice([120, 180, 181, 200])  # W031 (actual ~= 180)


def m_remaining_term(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["remainingTermMonths"] = rng.choice([60, 90, 91, 120])  # W030 (as_of=assertedDate)


def m_noiasof_after_asserted(p: dict[str, Any], rng: random.Random) -> None:
    p["deal"]["noiAsOfDate"] = "2026-09-30"  # W033 (after assertedDate 2026-08-15)


def m_expiration_before_commencement(p: dict[str, Any], rng: random.Random) -> None:
    p["lease"]["expiration"] = "2018-01-01"  # W034


def m_self_supersede(p: dict[str, Any], rng: random.Random) -> None:
    from openom_core.canonical import payload_hash

    p.setdefault("meta", {})
    stripped = {k: v for k, v in p.items() if k != "meta"}
    stripped["meta"] = {k: v for k, v in p["meta"].items() if k != "supersedes"}
    p["meta"]["supersedes"] = payload_hash(stripped)  # W050


_MUTATORS: list[Delta] = [
    m_caprate, m_caprate_band, m_priceperSF, m_noi_nonpositive, m_proforma,
    m_i003_skipped_crosscheck, m_currency_nonus, m_net_lease_landlord, m_gross_lease,
    m_rent_year1_vs_noi, m_rentpsf, m_monthly,
    m_source_verified, m_source_absent, m_escalation, m_period_gap_overlap, m_period_outside_term,
    m_term_months, m_remaining_term, m_noiasof_after_asserted, m_expiration_before_commencement,
    m_self_supersede,
]


def _findings(payload: dict[str, Any]) -> list[list[str]] | None:
    """Return the sorted [code, path] set for the warning+info tiers, or None if any schema error
    fires (a schema-invalid vector is out of scope for the consistency differential)."""
    report = validate(payload, schema=_SCHEMA)
    if report.errors:
        return None
    pairs = [[f.code, f.path] for f in (*report.warnings, *report.info)]
    return sorted(pairs)


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    corpus: list[dict[str, Any]] = []
    expected: list[list[list[str]]] = []
    covered: set[str] = set()

    # The clean skeleton itself (a no-finding baseline) plus boundary-mutated variants.
    attempts = 0
    while len(corpus) < COUNT and attempts < COUNT * 40:
        attempts += 1
        payload = _base()
        # self-supersede must run last (it hashes the finished payload); apply it separately.
        chosen = rng.sample(_MUTATORS, k=rng.randint(1, 3))
        do_supersede = m_self_supersede in chosen
        for mut in chosen:
            if mut is not m_self_supersede:
                mut(payload, rng)
        if do_supersede:
            m_self_supersede(payload, rng)
        findings = _findings(payload)
        if findings is None:
            continue
        corpus.append(payload)
        expected.append(findings)
        covered.update(code for code, _ in findings)

    # Prepend the untouched skeleton as an explicit "clean payload -> no findings" anchor.
    base = _base()
    corpus.insert(0, base)
    expected.insert(0, _findings(base) or [])

    (OUT / "corpus.jsonl").write_text(
        "".join(json.dumps(p, separators=(",", ":"), ensure_ascii=False) + "\n" for p in corpus),
        encoding="utf-8",
    )
    (OUT / "expected.jsonl").write_text(
        "".join(json.dumps(f, separators=(",", ":")) + "\n" for f in expected),
        encoding="utf-8",
    )
    print(f"wrote {len(corpus)} vectors to {OUT}")
    print(f"covered {len(covered)} finding codes: {', '.join(sorted(covered))}")


if __name__ == "__main__":
    main()
