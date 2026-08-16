"""Task 5: embed/read round-trip (spec §D)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from openom_core.canonical import canonicalize
from openom_core.embed import MAX_PAYLOAD_BYTES, embed, read
from openom_core.errors import PayloadTooLargeError
from openom_core.xmp import write_marker

SPEC = Path(__file__).resolve().parents[2] / "spec"
FIXED_DATE = "2026-08-15"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


@pytest.fixture
def base_pdf() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_roundtrip(base_pdf: bytes) -> None:
    sample = _sample()
    result = read(embed(base_pdf, sample, asserted_date=FIXED_DATE))
    assert result.present is True
    assert result.hash_valid is True
    assert result.origin_verified is None and result.signature_valid is None
    # value equality via canonical form (json round-trip normalizes 12.70->12.7 etc.)
    assert canonicalize(result.payload) == canonicalize(sample)  # type: ignore[arg-type]


def test_roundtrip_on_real_native_om(native_om: bytes) -> None:
    sample = _sample()
    result = read(embed(native_om, sample, asserted_date=FIXED_DATE))
    assert result.present is True and result.hash_valid is True


def test_om_json_named_and_af_present(base_pdf: bytes) -> None:
    embedded = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        assert "om.json" in pdf.attachments
        assert "/AF" in pdf.Root
        assert len(pdf.Root.AF) == 1


def test_subtype_name_escaped(base_pdf: bytes) -> None:
    embedded = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        ef = pdf.attachments["om.json"].obj.EF
        assert ef.F.Subtype == pikepdf.Name("/application/ld+json")


def test_stored_bytes_are_exact_jcs(base_pdf: bytes) -> None:
    sample = _sample()
    embedded = embed(base_pdf, sample, asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        raw = pdf.attachments["om.json"].get_file().read_bytes()
    assert raw == canonicalize(sample)


def test_tamper_detected(base_pdf: bytes) -> None:
    embedded = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        write_marker(
            pdf,
            spec_version="0.1",
            payload_filename="om.json",
            payload_hash="sha256:" + "0" * 64,
            asserted_date=FIXED_DATE,
        )
        buf = io.BytesIO()
        pdf.save(buf)
        tampered = buf.getvalue()
    result = read(tampered)
    assert result.present is True
    assert result.hash_valid is False


def test_absent_payload(base_pdf: bytes) -> None:
    result = read(base_pdf)
    assert result.present is False
    assert result.payload is None and result.hash_valid is None


def test_oversized_payload_rejected(base_pdf: bytes) -> None:
    big = {"x": "A" * (MAX_PAYLOAD_BYTES + 10)}
    with pytest.raises(PayloadTooLargeError) as ei:
        embed(base_pdf, big, asserted_date=FIXED_DATE)
    assert ei.value.code == "OM-IO-BOMB"


def test_double_embed_does_not_stack(base_pdf: bytes) -> None:
    once = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    twice = embed(once, _sample(), asserted_date="2026-08-16")
    with pikepdf.open(io.BytesIO(twice)) as pdf:
        assert len(pdf.Root.AF) == 1
        names = list(pdf.attachments)
        assert names.count("om.json") == 1
    assert read(twice).hash_valid is True
