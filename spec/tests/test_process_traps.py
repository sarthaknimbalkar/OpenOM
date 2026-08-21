"""M4 #55: prove the warning-iteration loop the playbook relies on. Each case is a realistic
mis-extraction of the demo OM that a naive first pass would produce; om_validate MUST flag it with
a specific OMW-W### (the agent's cue to re-read the source), and the corrected demo payload
(expected-payload.json) MUST be warning-clean. This is the machine-checked form of "a warning means
your extraction is probably wrong - fix it, don't silence it."
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
BASE = json.loads((ROOT / "process" / "example" / "expected-payload.json").read_text("utf-8"))
SCHEMA = json.loads((SPEC / "om-0.1.schema.json").read_text("utf-8"))


def _warn_codes(payload: dict) -> set[str]:
    return {w.code for w in validate(payload, schema=SCHEMA).warnings}


def test_corrected_demo_payload_is_warning_clean() -> None:
    # The "after" of every trap: the reviewed demo payload trips nothing.
    assert _warn_codes(BASE) == set()


def test_caprate_percent_trap() -> None:
    # Naive: transcribed "5.75%" as 5.75 instead of the decimal 0.0575.
    trap = copy.deepcopy(BASE)
    trap["deal"]["capRate"] = 5.75
    codes = _warn_codes(trap)
    assert "OMW-W013" in codes  # capRate outside the [0.02, 0.20] plausibility band


def test_rent_schedule_gap_trap() -> None:
    # Naive: mis-read the second period's start, leaving a hole in coverage.
    trap = copy.deepcopy(BASE)
    trap["lease"]["rentSchedule"][1]["periodStart"] = "2027-01-01"
    assert "OMW-W021" in _warn_codes(trap)


def test_nnn_but_landlord_pays_trap() -> None:
    # Naive: marked a landlord responsibility true while calling the lease NNN.
    trap = copy.deepcopy(BASE)
    trap["lease"]["landlordResponsibilities"]["taxes"] = True
    assert "OMW-W040" in _warn_codes(trap)


def test_rent_psf_mismatch_trap() -> None:
    # Naive: fat-fingered a rent/SF figure that no longer ties to annualRent / buildingSF.
    trap = copy.deepcopy(BASE)
    trap["lease"]["rentSchedule"][0]["rentPSF"] = 30.00
    assert "OMW-W024" in _warn_codes(trap)


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda p: p["deal"].__setitem__("noi", 200000), "OMW-W010"),   # noi no longer ties to cap
        (lambda p: p["deal"].__setitem__("pricePerSF", 999), "OMW-W011"),  # price/SF off
    ],
)
def test_deal_math_traps(mutate, expected: str) -> None:
    trap = copy.deepcopy(BASE)
    mutate(trap)
    assert expected in _warn_codes(trap)
