"""M4 #59: the reprice/re-embed loop the playbook prescribes — om_read the prior payload, build a
new one with meta.supersedes = the prior hash, om_embed (replace, never stack). Proves the
supersedes chain end-to-end and that a re-embed leaves exactly one payload.
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.canonical import payload_hash
from openom_core.embed import embed, read
from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
EXAMPLE = ROOT / "process" / "example"
SCHEMA = json.loads((SPEC / "om-0.1.schema.json").read_text("utf-8"))
PRIOR = json.loads((EXAMPLE / "expected-payload.json").read_text("utf-8"))
REPRICED = json.loads((EXAMPLE / "repriced-payload.json").read_text("utf-8"))


def test_repriced_payload_is_valid_and_consistent() -> None:
    report = validate(REPRICED, schema=SCHEMA)
    assert report.errors == []
    assert [w.code for w in report.warnings] == []


def test_repriced_supersedes_points_at_prior_payload() -> None:
    assert REPRICED["meta"]["supersedes"] == payload_hash(PRIOR)


def test_reprice_round_trip_replaces_not_stacks() -> None:
    pdf = (EXAMPLE / "sample-om.pdf").read_bytes()
    first = embed(pdf, PRIOR, asserted_date=PRIOR["assertedDate"])
    prior_hash = payload_hash(read(first).payload)  # hash of what was actually embedded
    assert REPRICED["meta"]["supersedes"] == prior_hash  # the chain link the playbook sets

    second = embed(first, REPRICED, asserted_date=REPRICED["assertedDate"])
    result = read(second)
    assert result.present is True and result.hash_valid is True
    assert result.payload["deal"]["askingPrice"] == 2400000  # the new payload won
    assert result.payload["meta"]["supersedes"] == prior_hash

    import io

    import pikepdf

    with pikepdf.open(io.BytesIO(second)) as doc:
        names = doc.Root.Names.EmbeddedFiles.Names
        om_entries = [n for n in names[0::2] if str(n) == "om.json"]
    assert len(om_entries) == 1  # re-embed replaced in place; never stacked
