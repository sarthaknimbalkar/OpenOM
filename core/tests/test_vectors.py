"""Task 3: /core reproduces every committed vector, and the schema validates the samples.

This is the contract Track B pins to. The oracle is anchored: the ``cafe`` vector's hash is
asserted equal to the value published independently in the spec (§C.1), so a wrong canonical
in *both* implementations cannot pass silently.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import jsonschema
import pytest

from openom_core.canonical import canonicalize, hash_bytes

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec"
VECTORS = SPEC / "vectors"

# Independently published in the handoff spec §C.1 for {"tenantEntity":"café"} (NFC).
SPEC_CAFE_HASH = "sha256:851b8c23eb02709cb52f013fff5215d8b1d836fa2283fbf8e7c35dbbc5a48ddf"


def _payload_names() -> list[str]:
    return sorted(p.stem for p in (VECTORS / "payloads").glob("*.json"))


@pytest.mark.parametrize("name", _payload_names())
def test_core_reproduces_vector(name: str) -> None:
    payload = json.loads((VECTORS / "payloads" / f"{name}.json").read_text(encoding="utf-8"))
    expected = json.loads((VECTORS / "expected" / f"{name}.json").read_text(encoding="utf-8"))
    jcs = canonicalize(payload)
    assert hash_bytes(jcs) == expected["jcs_sha256"]
    assert base64.b64encode(jcs).decode("ascii") == expected["jcs_b64"]


def test_cafe_anchored_to_spec() -> None:
    payload = json.loads((VECTORS / "payloads" / "cafe.json").read_text(encoding="utf-8"))
    assert hash_bytes(canonicalize(payload)) == SPEC_CAFE_HASH


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_accepts_valid_sample() -> None:
    schema = _load(SPEC / "om-0.1.schema.json")
    jsonschema.validate(_load(SPEC / "samples" / "valid-stnl.json"), schema)


@pytest.mark.parametrize(
    "bad",
    ["invalid-missing-noitype", "invalid-populated-signature", "invalid-caprate-percentage"],
)
def test_schema_rejects_invalid_samples(bad: str) -> None:
    schema = _load(SPEC / "om-0.1.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_load(SPEC / "samples" / f"{bad}.json"), schema)
