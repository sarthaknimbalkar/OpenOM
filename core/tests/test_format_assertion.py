"""[Mi33] The schema relies on `format` assertion (draft 2020-12 makes format annotation-only by
default). The conformance oracle MACHINE-ENFORCES this: the invalid-bad-date sample is a tripwire a
naive validator (no FormatChecker) silently PASSES but a conformant one REJECTS. This locks that
discriminating property so the format-assertion requirement can never quietly become unenforced.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "spec" / "om-0.1.schema.json").read_text(encoding="utf-8"))
BAD = json.loads((ROOT / "spec" / "samples" / "invalid-bad-date.json").read_text(encoding="utf-8"))


def test_bad_date_is_a_format_assertion_tripwire() -> None:
    naive = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(BAD))
    conformant = list(
        jsonschema.Draft202012Validator(
            SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(BAD)
    )
    assert not naive, "sample no longer discriminates - a non-asserting impl would still fail it"
    assert conformant, "a conformant (format-asserting) validator MUST reject the bad date"


def test_manifest_marks_it_invalid() -> None:
    manifest = json.loads((ROOT / "spec" / "samples" / "manifest.json").read_text(encoding="utf-8"))
    entry = next(s for s in manifest["samples"] if s["name"] == "invalid-bad-date")
    assert entry["valid"] is False and "OMV-E001" in entry["errorCodes"]
