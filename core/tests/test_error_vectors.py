"""Python side of the error differential corpus (the schema-error-tier anti-fork).

Locks the Python core to its committed golden error vectors: each invalid payload must reproduce the
exact {code, path} error set in expected.jsonl. The matching js/test/error-vectors.test.ts
asserts the JS core (ajv) reproduces the SAME sets - proving the two different schema engines agree
on the finding list, not just the block/allow verdict. Regenerate with
core/scripts/gen_error_corpus.py after any error-tier or schema change.
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.schema import load_schema
from openom_core.validate import validate

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors" / "errors"
_SCHEMA = load_schema()


def _lines(name: str) -> list[str]:
    return [ln for ln in (VECTORS / name).read_text(encoding="utf-8").splitlines() if ln]


def test_python_reproduces_the_committed_error_sets() -> None:
    corpus = _lines("corpus.jsonl")
    expected = _lines("expected.jsonl")
    assert len(corpus) == len(expected)
    assert len(corpus) >= 10
    mismatches: list[str] = []
    for payload_line, expected_line in zip(corpus, expected, strict=True):
        case = json.loads(payload_line)
        report = validate(case["payload"], schema=_SCHEMA)
        assert report.errors, f"{case['name']} produced no errors"
        got = sorted([f.code, f.path] for f in report.errors)
        want = json.loads(expected_line)
        if got != want:
            mismatches.append(f"{case['name']}: {got} != {want}")
    assert mismatches == []
