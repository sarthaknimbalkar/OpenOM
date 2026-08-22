"""[Ma2] `validate(payload)` with no schema MUST perform full schema validation.

The old default (schema=None -> a two-rule subset) silently skipped every structural/type/required/
format error, so a naive programmatic caller could get ok/no-errors on a schema-invalid payload. The
default now loads the bundled schema; these guard that a schema-invalid payload is caught with NO
schema argument, that a valid payload still passes, and that an explicit schema still works.
"""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.validate import validate

SAMPLES = Path(__file__).resolve().parents[2] / "spec" / "samples"


def _sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def test_no_schema_arg_catches_a_structurally_invalid_payload() -> None:
    # Missing @context is a schema `required` violation the old two-rule subset ignored entirely.
    report = validate(_sample("invalid-missing-context"))
    assert report.errors, "validate(payload) with no schema must surface schema errors"


def test_no_schema_arg_catches_a_bad_format() -> None:
    report = validate(_sample("invalid-bad-date"))
    assert report.errors


def test_no_schema_arg_accepts_a_valid_payload() -> None:
    report = validate(_sample("valid-stnl"))
    assert not report.errors


def test_explicit_schema_still_works() -> None:
    from openom_core.schema import load_schema

    report = validate(_sample("valid-stnl"), schema=load_schema())
    assert not report.errors
