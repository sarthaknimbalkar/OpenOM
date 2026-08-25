"""Python side of the consistency differential corpus (the warning/info-tier anti-fork).

Locks the Python core against its own committed golden corpus: re-validating each vector must
reproduce the exact {code, path} finding set in expected.jsonl. A drift here means a consistency
rule changed without regenerating (run core/scripts/gen_consistency_corpus.py). The matching
js/test/consistency-vectors.test.ts asserts the JS core reproduces the SAME sets - that is the
cross-implementation guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.schema import load_schema
from openom_core.validate import validate

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors" / "consistency"
_SCHEMA = load_schema()


def _lines(name: str) -> list[str]:
    return [ln for ln in (VECTORS / name).read_text(encoding="utf-8").splitlines() if ln]


def test_python_reproduces_the_committed_finding_sets() -> None:
    corpus = _lines("corpus.jsonl")
    expected = _lines("expected.jsonl")
    assert len(corpus) == len(expected)
    assert len(corpus) >= 300
    mismatches: list[str] = []
    for i, (payload_line, expected_line) in enumerate(zip(corpus, expected, strict=True)):
        payload = json.loads(payload_line)
        report = validate(payload, schema=_SCHEMA)
        assert report.errors == [], f"vector {i} is not schema-valid: {report.errors}"
        got = sorted([f.code, f.path] for f in (*report.warnings, *report.info))
        want = json.loads(expected_line)
        if got != want:
            mismatches.append(f"vector {i}: {got} != {want}")
    assert mismatches == []
