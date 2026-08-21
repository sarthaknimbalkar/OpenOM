"""[OM-DoD-002] M1.x validator gate: the standalone consistency checker MUST detect every
seeded defect in a labeled corpus with **zero false negatives**, on a payload alone (no schema,
no PDF, no network, no inference). The corpus is selected with ``--corpus`` (default
``fixtures/seeded_defects``):

    pytest core/tests/test_consistency.py --corpus fixtures/seeded_defects

Each case applies a small labeled mutation to a clean base payload and lists the §H code(s) it
MUST raise. The base itself is internally consistent, so the gate also asserts the base is clean
of every code any case expects - proving the detections are caused by the seeded defect, not by
an always-on check.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from openom_core.canonical import payload_hash
from openom_core.validate import validate

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_manifest(corpus_dir: Path) -> dict[str, Any]:
    manifest = corpus_dir / "manifest.json"
    if not manifest.exists():
        pytest.skip(f"no seeded-defect corpus at {manifest}")
    data: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
    return data


def _set_pointer(doc: Any, pointer: str, value: Any) -> None:
    parts = pointer.strip("/").split("/")
    node = doc
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    key: Any = int(parts[-1]) if isinstance(node, list) else parts[-1]
    node[key] = value


def _del_pointer(doc: Any, pointer: str) -> None:
    parts = pointer.strip("/").split("/")
    node = doc
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    key: Any = int(parts[-1]) if isinstance(node, list) else parts[-1]
    del node[key]


def _apply_case(base: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(base)
    for mut in case.get("mutations", []):
        if mut.get("delete"):
            _del_pointer(payload, mut["path"])
        else:
            _set_pointer(payload, mut["path"], mut["value"])
    if case.get("selfSupersede"):
        stripped = copy.deepcopy(payload)
        stripped["meta"].pop("supersedes", None)
        payload["meta"]["supersedes"] = payload_hash(stripped)
    return payload


def _cases(corpus_dir: Path) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    manifest = _load_manifest(corpus_dir)
    base = json.loads((REPO_ROOT / manifest["base"]).read_text(encoding="utf-8"))
    return [(c["name"], base, c) for c in manifest["cases"]]


def test_base_is_clean_of_every_expected_code(corpus_dir: Path) -> None:
    """The base payload must raise NONE of the codes any case seeds (no always-on checks)."""
    manifest = _load_manifest(corpus_dir)
    base = json.loads((REPO_ROOT / manifest["base"]).read_text(encoding="utf-8"))
    seeded = {code for c in manifest["cases"] for code in c["expect"]}
    got = {f.code for f in validate(base).warnings}
    leaked = seeded & got
    assert not leaked, f"base already raises seeded codes (false positives): {sorted(leaked)}"


def test_seeded_defects_detected_with_zero_false_negatives(corpus_dir: Path) -> None:
    """Every case's expected §H code(s) MUST be present - the DoD-002 zero-false-negative gate."""
    misses: dict[str, list[str]] = {}
    for name, base, case in _cases(corpus_dir):
        payload = _apply_case(base, case)
        report = validate(payload, as_of=case.get("asOf"))
        got_warn = {f.code for f in report.warnings}
        got_info = {f.code for f in report.info}
        missing = [c for c in case["expect"] if c not in got_warn]
        missing += [c for c in case.get("expectInfo", []) if c not in got_info]
        if missing:
            misses[name] = missing
    assert not misses, f"seeded defects NOT detected (false negatives): {misses}"
