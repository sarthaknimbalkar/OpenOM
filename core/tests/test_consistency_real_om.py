"""[#9][M2] Demonstrate the consistency validator on a **real-OM-derived** payload.

The seeded-defect gate (``test_consistency.py``) proves zero-false-negative detection on a
synthetic JSON base. This gate closes the adoption residual: it extracts the payload from a real
*embedded* OM PDF (``spec/assets/openom-sample.pdf`` - the same file shipped on openom.app and
dropped into ``/verify/``) via the deterministic read path, then shows the validator (a) passes the
genuinely-consistent shipped assertion clean, and (b) catches genuine broker inconsistencies
*derived from those real numbers* - the exact "does the math add up" failures a real OM would carry.

Deterministic, offline, no inference. The mutations are computed against the real extracted values
(NOI 115,625 / price 1,850,000 = 6.25% cap; rentPSF 12.70 = 115,625 / 9,100 SF; the 10% option
step), so each expected code is caused by the seeded inconsistency, not by an always-on check.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from openom_core.embed import read
from openom_core.validate import validate

SAMPLE_OM = Path(__file__).resolve().parents[2] / "spec" / "assets" / "openom-sample.pdf"


def _real_payload() -> dict[str, Any]:
    if not SAMPLE_OM.exists():
        pytest.skip(f"no embedded sample OM at {SAMPLE_OM}")
    result = read(SAMPLE_OM.read_bytes())
    assert result.present, "sample OM must carry an embedded openOM payload"
    assert isinstance(result.payload, dict)
    return result.payload


def test_real_om_extracts_and_validates_clean() -> None:
    """The shipped, human-reviewed assertion is schema-valid and consistency-clean."""
    payload = _real_payload()
    report = validate(payload)
    assert report.ok, [f.code for f in report.errors]
    assert not report.warnings, [f.code for f in report.warnings]


def _set_cap(p: dict[str, Any]) -> None:
    p["deal"]["capRate"] = 0.09  # NOI/price imply 6.25%; 9% is the classic mismatch


def _set_ppsf(p: dict[str, Any]) -> None:
    p["deal"]["pricePerSF"] = 999  # price/SF ≈ $203; $999 contradicts it


def _set_rentpsf(p: dict[str, Any]) -> None:
    p["lease"]["rentSchedule"][0]["rentPSF"] = 50  # must track annualRent/SF (12.70)


def _set_escalation(p: dict[str, Any]) -> None:
    p["lease"]["rentSchedule"][1]["escalationFromPrior"] = 0.5  # real step is 10%


def _set_gap(p: dict[str, Any]) -> None:
    p["lease"]["rentSchedule"][1]["periodStart"] = "2030-01-01"  # leaves a gap


# Each genuine broker inconsistency, derived from the real extracted numbers, and the §H code it
# MUST raise. The clean baseline (above) raises none of these, so a hit is caused by the mutation.
_CASES: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
    ("cap-rate vs NOI/price", "OMW-W010", _set_cap),
    ("price-per-SF", "OMW-W011", _set_ppsf),
    ("rentPSF vs annualRent/SF", "OMW-W024", _set_rentpsf),
    ("escalation step", "OMW-W023", _set_escalation),
    ("rent-schedule gap", "OMW-W021", _set_gap),
]


@pytest.mark.parametrize("label,code,mutate", _CASES, ids=[c[0] for c in _CASES])
def test_real_om_derived_inconsistency_is_caught(
    label: str, code: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    payload = copy.deepcopy(_real_payload())
    mutate(payload)
    report = validate(payload)
    got = {f.code for f in report.warnings}
    assert code in got, f"{label}: expected {code}, got {sorted(got)}"
