"""M4 gate [OM-DoD-005]: the payload the /process playbook produces from the demo OM passes
om_validate with zero errors AND is internally consistent (zero warnings) - the CI-checkable form
of "the playbook drives the full loop to a valid payload". Also asserts the demo OM is something to
extract FROM (no embedded payload), not an already-embedded OM.
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.embed import read
from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
EXAMPLE = ROOT / "process" / "example"


def _schema() -> dict:
    return json.loads((SPEC / "om-0.1.schema.json").read_text(encoding="utf-8"))


def test_process_example_payload_is_valid_and_consistent() -> None:
    payload = json.loads((EXAMPLE / "expected-payload.json").read_text(encoding="utf-8"))
    report = validate(payload, schema=_schema())
    assert report.errors == [], f"schema errors: {[e.code for e in report.errors]}"
    assert [w.code for w in report.warnings] == [], (
        f"consistency warnings (the playbook's job to resolve): "
        f"{[(w.code, w.path) for w in report.warnings]}"
    )


def test_example_rent_periods_are_asserted_post_review() -> None:
    # The review gate promotes extracted -> asserted; the reviewed payload reflects that.
    payload = json.loads((EXAMPLE / "expected-payload.json").read_text(encoding="utf-8"))
    for period in payload["lease"]["rentSchedule"]:
        assert period["source"] == "asserted"


def test_sample_om_has_no_embedded_payload() -> None:
    # The demo doc is an OM to extract FROM, not an already-embedded openOM.
    assert read((EXAMPLE / "sample-om.pdf").read_bytes()).present is False


def test_scanned_demo_om_classifies_scanned() -> None:
    # The image-only variant drives the playbook's scanned/OCR branch (#58).
    from openom_core.inspect import inspect

    data = (EXAMPLE / "sample-om-scanned.pdf").read_bytes()
    assert inspect(data)["class"] == "scanned"
    assert read(data).present is False
