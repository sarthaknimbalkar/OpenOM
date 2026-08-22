"""[Ma3] The Python payload TypedDicts MUST stay in lock-step with spec/om-0.1.schema.json — each
TypedDict's keys equal the schema's properties at that path, so the typed view can't drift from the
contract (the same guarantee /js gets from its generated payload-types.ts)."""

from __future__ import annotations

import json
from pathlib import Path

from openom_core.types import AssertedBy, Deal, Meta, OMPayload, Property

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "spec" / "om-0.1.schema.json"
SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _props(path: list[str]) -> set[str]:
    node = SCHEMA
    for p in path:
        node = node["properties"][p]
    return set((node.get("properties") or {}).keys())


def test_typeddicts_match_schema_properties() -> None:
    cases = [
        (OMPayload, []),
        (AssertedBy, ["assertedBy"]),
        (Deal, ["deal"]),
        (Property, ["property"]),
        (Meta, ["meta"]),
    ]
    for td, path in cases:
        keys = set(td.__annotations__)
        schema_props = _props(path)
        assert keys == schema_props, (
            f"{td.__name__} keys drifted from schema at {path or 'top'}: "
            f"only-in-type={keys - schema_props}, only-in-schema={schema_props - keys}"
        )
