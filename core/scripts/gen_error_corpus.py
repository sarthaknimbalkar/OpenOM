#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate the cross-language ERROR-tier differential corpus (the schema-error anti-fork).

The consistency (warning/info) tier is hand-written in both cores. The error tier is delegated to
two DIFFERENT JSON Schema engines - jsonschema (Python) and ajv (JS) - which enumerate schema errors
differently, so their finding LISTS forked even though the block/allow verdict agreed. This is
a curated set of INVALID payloads plus the canonical sorted {code, path} set Python emits after the
shared normal form (required errors at the missing child per RFC 6901; redundant ancestor OMV-E001
suppressed). Both cores must reproduce the SAME set: core/tests/test_error_vectors.py guards Python,
js/test/error-vectors is the anti-fork assertion.

NaN/Infinity are covered by dedicated unit tests, not here (they can't live in a JSON file).

Run after any error-tier / schema change:  python core/scripts/gen_error_corpus.py
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openom_core.schema import load_schema
from openom_core.validate import validate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "spec" / "vectors" / "errors"
SKELETON = ROOT / "spec" / "samples" / "valid-stnl.json"
_SCHEMA = load_schema()


def _base() -> dict[str, Any]:
    return json.loads(SKELETON.read_text(encoding="utf-8"))


# Each recipe returns an INVALID payload exercising one error class. A recipe returning a non-dict
# (the whole-document case) is allowed. Curated (not random) so the corpus is legible + stable.
def _drop(key: str) -> Callable[[], Any]:
    def r() -> Any:
        p = _base()
        p.pop(key, None)
        return p
    return r


RECIPES: dict[str, Callable[[], Any]] = {
    "non-object-document": lambda: [1, 2, 3],
    "deal-not-object": lambda: {**_base(), "deal": "nope"},
    "meta-not-object": lambda: {**_base(), "meta": "nope"},
    "property-not-object": lambda: {**_base(), "property": 5},
    "missing-meta": _drop("meta"),
    "missing-asserted-by": _drop("assertedBy"),
    "missing-asserted-date": _drop("assertedDate"),
    "whitespace-asserted-by": lambda: {
        **_base(), "assertedBy": {"broker": " ", "brokerage": " ", "license": " "}
    },
    "caprate-percentage": lambda: {**_base(), "deal": {**_base()["deal"], "capRate": 6.25}},
    "missing-noitype": lambda: {**_base(), "deal": {"noi": 100000, "status": "active"}},
    "malformed-supersedes": lambda: {**_base(), "meta": {"supersedes": "not-a-hash"}},
    "populated-signature": lambda: {
        **_base(), "meta": {"supersedes": None, "signature": {"bogus": 1}}
    },
    "out-of-range-int": lambda: {**_base(), "ext": {"acme": {"bigId": 2**53}}},
    "bad-date-format": lambda: {**_base(), "assertedDate": "08/15/2026"},
}


def _finding_set(payload: Any) -> list[list[str]]:
    report = validate(payload, schema=_SCHEMA)
    return sorted([f.code, f.path] for f in report.errors)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    corpus: list[dict[str, Any]] = []
    expected: list[list[list[str]]] = []
    for name in sorted(RECIPES):
        payload = RECIPES[name]()
        findings = _finding_set(payload)
        assert findings, f"recipe {name} produced no errors (not an invalid payload?)"
        corpus.append({"name": name, "payload": payload})
        expected.append(findings)

    (OUT / "corpus.jsonl").write_text(
        "".join(json.dumps(c, separators=(",", ":"), ensure_ascii=False) + "\n" for c in corpus),
        encoding="utf-8",
    )
    (OUT / "expected.jsonl").write_text(
        "".join(json.dumps(f, separators=(",", ":")) + "\n" for f in expected),
        encoding="utf-8",
    )
    codes = sorted({c for f in expected for c, _ in f})
    print(f"wrote {len(corpus)} error vectors to {OUT}")
    print(f"covered codes: {', '.join(codes)}")


if __name__ == "__main__":
    main()
