"""[#3][OM-EMB-020] A signed OM must survive embed: the payload is appended via an incremental
save so the signature's byte range stays cryptographically intact, instead of the default
full-rewrite (which invalidates it).

The fixture ``signed-approval.pdf`` is a genuinely-signed PDF (self-signed approval signature,
committed; regenerate with ``fixtures/gen_signed_fixture.py``). Signature preservation is proven by
**byte-range integrity**: a byte-range (/ByteRange) signature covers bytes wholly within the signed
file, so an incremental append that preserves the entire original as a byte-exact prefix cannot
alter any signed byte. The test asserts that prefix preservation directly; when pyhanko is present
it *additionally* cryptographically validates ``.intact`` for belt-and-suspenders rigor.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pikepdf
import pytest

from openom_core.embed import _is_signed, embed, read
from openom_core.errors import SignedEmbedError

SIGNED_OM = Path(__file__).resolve().parent / "fixtures" / "signed-approval.pdf"

_PAYLOAD = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "assertedBy": {"broker": "Jane Example"},
    "assertedDate": "2026-08-24",
    "deal": {"status": "active"},
}


def _signed_bytes() -> bytes:
    if not SIGNED_OM.exists():
        pytest.skip(f"no signed fixture at {SIGNED_OM} (run gen_signed_fixture.py)")
    return SIGNED_OM.read_bytes()


def _crypto_intact(pdf: bytes) -> bool | None:
    """Cryptographically validate the first signature's byte range, or None if pyhanko is absent."""
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext
    except ImportError:
        return None
    reader = PdfFileReader(io.BytesIO(pdf))
    sigs = reader.embedded_signatures
    if not sigs:
        return False
    logging.disable(logging.CRITICAL)  # silence self-signed trust-path warnings (not our concern)
    try:
        status = validate_pdf_signature(
            sigs[0], ValidationContext(allow_fetching=False, trust_roots=[])
        )
    finally:
        logging.disable(logging.NOTSET)
    return bool(status.intact)


def test_fixture_is_detected_as_signed() -> None:
    with pikepdf.open(io.BytesIO(_signed_bytes())) as pdf:
        assert _is_signed(pdf)


def test_embed_preserves_signature_and_payload() -> None:
    signed = _signed_bytes()
    out = embed(signed, _PAYLOAD, asserted_date="2026-08-24")

    # The signed bytes are preserved byte-exact as a prefix (a true incremental append) - which
    # means every byte the /ByteRange signs is unchanged, i.e. the signature stays intact.
    assert out.startswith(signed), "embed must append to a signed PDF, not rewrite it"
    crypto = _crypto_intact(out)
    if crypto is not None:  # extra proof when pyhanko is installed
        assert crypto, "incremental embed must not invalidate the signature"

    # The payload round-trips with a valid integrity hash + full attachment structure.
    result = read(out)
    assert result.present
    assert result.hash_valid is True
    assert result.source_doc_hash is not None
    with pikepdf.open(io.BytesIO(out)) as pdf:
        assert "/AF" in pdf.Root
        assert str(pdf.Root.AF[0].EF.F.Subtype) == "/application/ld+json"


def test_repaired_signed_pdf_is_refused_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A signed OM whose xref pymupdf rebuilds on open cannot be appended safely - refuse with
    a typed OM-EMB-021 instead of an unmapped fitz crash or a silently-broken signature."""
    import pymupdf

    class _Repaired:
        is_repaired = True

        def close(self) -> None:
            pass

    monkeypatch.setattr(pymupdf, "open", lambda *a, **k: _Repaired())
    with pytest.raises(SignedEmbedError) as e:
        embed(_signed_bytes(), _PAYLOAD, asserted_date="2026-08-24")
    assert e.value.code == "OM-EMB-021"


def test_unsigned_input_uses_full_rewrite() -> None:
    """A plain PDF is not detected as signed and still round-trips (default path untouched)."""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Plain OM")
    plain = doc.tobytes()
    doc.close()

    with pikepdf.open(io.BytesIO(plain)) as pdf:
        assert not _is_signed(pdf)
    out = embed(plain, _PAYLOAD, asserted_date="2026-08-24")
    assert not out.startswith(plain)  # a full rewrite, not an append
    assert read(out).hash_valid is True


def test_signed_embed_is_idempotent() -> None:
    """Re-embedding into an already-embedded signed OM stays intact and readable, with no stacked
    payload: exactly one om.json /AF entry."""
    signed = _signed_bytes()
    once = embed(signed, _PAYLOAD, asserted_date="2026-08-24")
    twice = embed(once, _PAYLOAD, asserted_date="2026-08-24")

    assert twice.startswith(signed)  # still an append over the original signed bytes
    crypto = _crypto_intact(twice)
    if crypto is not None:
        assert crypto
    assert read(twice).hash_valid is True
    with pikepdf.open(io.BytesIO(twice)) as pdf:
        af_names = [str(f.F) for f in pdf.Root.AF]
        assert af_names.count("om.json") == 1
