"""M4 #56: drift-lock process/mapping-guide.md to the schema + validator. The guide hand-lists field
paths, controlled-vocabulary values, and OMW/OMV/OMI codes; these silently rot when the schema or
validator change (the same class of bug drift-locked for the @context, #13). These offline tests
fail if the guide and the machine artifacts diverge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openom_core.validate import _REQUIREMENT

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
GUIDE = (ROOT / "process" / "mapping-guide.md").read_text(encoding="utf-8")
SCHEMA = json.loads((SPEC / "om-0.1.schema.json").read_text(encoding="utf-8"))

# Structural/reserved fields the extractor never maps (set by tooling / const / reserved), so the
# guide is not expected to describe them as extraction targets.
_STRUCTURAL = {"specVersion", "signature"}


def _schema_property_names(node: Any, acc: set[str]) -> None:
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            acc.update(k for k in props if not k.startswith("@"))
        for v in node.values():
            _schema_property_names(v, acc)
    elif isinstance(node, list):
        for item in node:
            _schema_property_names(item, acc)


def _schema_enum_values(node: Any, acc: set[str]) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("enum"), list):
            acc.update(str(v) for v in node["enum"])
        for v in node.values():
            _schema_enum_values(v, acc)
    elif isinstance(node, list):
        for item in node:
            _schema_enum_values(item, acc)


def test_guide_covers_every_extractable_schema_field() -> None:
    names: set[str] = set()
    _schema_property_names(SCHEMA, names)
    missing = {n for n in names - _STRUCTURAL if n not in GUIDE}
    assert not missing, f"schema fields absent from the mapping guide: {sorted(missing)}"


def test_guide_covers_every_controlled_vocabulary_value() -> None:
    values: set[str] = set()
    _schema_enum_values(SCHEMA, values)
    # short tokens (N, NN) are covered implicitly by the enum they belong to; check len>=3.
    missing = {v for v in values if len(v) >= 3 and v not in GUIDE}
    assert not missing, f"enum values absent from the mapping guide: {sorted(missing)}"


def test_every_code_named_in_the_guide_is_real() -> None:
    cited = set(re.findall(r"OM[VWI]-[EWI]\d{3}", GUIDE))
    known = set(_REQUIREMENT)  # every validator error/warning/info code
    unknown = cited - known
    assert not unknown, f"guide cites codes the validator does not emit: {sorted(unknown)}"
    assert cited, "the guide should cite at least the consistency codes it explains"
