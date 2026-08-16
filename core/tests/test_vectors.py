"""Task 3: /core reproduces every committed vector, and the schema validates the samples.

This is the contract Track B pins to. The oracle is anchored: the ``cafe`` vector's hash is
asserted equal to the value published independently in the spec (§C.1), so a wrong canonical
in *both* implementations cannot pass silently.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pikepdf
import pytest

from openom_core.canonical import canonicalize, hash_bytes
from openom_core.embed import read
from openom_core.xmp import read_marker

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


# Schema-tier sample validation moved to test_samples.py (manifest-driven, format-asserting).


@pytest.mark.parametrize("name", _payload_names())
def test_golden_pdf_readback(name: str) -> None:
    """Task 12: Track-A golden PDFs read back correctly (the cross-impl gate, Track-A side)."""
    pdf_bytes = (VECTORS / "pdfs" / f"{name}.pdf").read_bytes()
    sidecar = json.loads((VECTORS / "pdfs" / f"{name}.expected.json").read_text(encoding="utf-8"))
    result = read(pdf_bytes)
    assert result.present is True
    assert result.hash_valid is True
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        assert list(pdf.attachments).count("om.json") == 1
        marker = read_marker(pdf)
        assert marker is not None
        assert marker["payloadHash"] == sidecar["payloadHash"]


@pytest.mark.parametrize("name", _payload_names())
def test_golden_pdf_wire_format(name: str) -> None:
    """The golden PDFs pin the on-wire structure the standard depends on ([OM-EMB-002/004/007]);
    any drift here is a silent cross-impl fork, so it fails loudly."""
    pdf_bytes = (VECTORS / "pdfs" / f"{name}.pdf").read_bytes()
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        spec = pdf.attachments["om.json"].obj
        assert "/AF" in pdf.Root  # associated-files array present
        assert any(f.objgen == spec.objgen for f in pdf.Root.AF)  # /AF -> this Filespec
        assert str(spec.get("/AFRelationship")) == "/Data"  # [OM-EMB relationship]
        ef = spec.EF
        assert ef.F.objgen == ef.UF.objgen  # /F and /UF share one stream ([OM-EMB-007])
        assert ef.F.Subtype == pikepdf.Name("/application/ld+json")  # [OM-EMB-004]
        raw = bytes(pdf.Root.Metadata.read_bytes())
        assert b"omspec:payloadHash" in raw  # conformant, namespaced marker (not unqualified)
        assert b"https://verveliolabs.com/openom/ns/0.1#" in raw
