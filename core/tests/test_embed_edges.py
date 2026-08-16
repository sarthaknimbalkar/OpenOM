"""Task 5 peak: detection order, decompression-bomb bounds, and survival through re-save."""

from __future__ import annotations

import io
import json
import zlib
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from openom_core.embed import (
    MAX_PAYLOAD_BYTES,
    _bounded_inflate,
    _find_ef_stream,
    embed,
    read,
)
from openom_core.errors import PayloadTooLargeError

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


def _resave(pdf_bytes: bytes, **save_kwargs: Any) -> bytes:
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, **save_kwargs)
        return buf.getvalue()


# --- detection order [OM-XMP-003] ------------------------------------------------------

def test_af_first_detection_without_name_tree(base_pdf: bytes) -> None:
    """Reader finds the payload via catalog /AF even when the EmbeddedFiles name tree is gone."""
    out = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(out)) as pdf:
        if "/Names" in pdf.Root and "/EmbeddedFiles" in pdf.Root.Names:
            del pdf.Root.Names.EmbeddedFiles
        assert "/AF" in pdf.Root
        buf = io.BytesIO()
        pdf.save(buf)
        stripped = buf.getvalue()
    result = read(stripped)
    assert result.present is True
    assert result.hash_valid is True


def test_fallback_to_name_tree_without_af(base_pdf: bytes) -> None:
    """Reader falls back to the EmbeddedFiles name tree for producers that omit /AF."""
    out = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(out)) as pdf:
        del pdf.Root.AF
        buf = io.BytesIO()
        pdf.save(buf)
        no_af = buf.getvalue()
    assert read(no_af).present is True


# --- survival through download / re-upload / optimizer --------------------------------

def test_survives_optimizer_resave(base_pdf: bytes) -> None:
    """Payload + marker survive a re-save that linearizes, uses object streams, recompresses."""
    out = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    optimized = _resave(
        out,
        linearize=True,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
        recompress_flate=True,
    )
    result = read(optimized)
    assert result.present is True
    assert result.hash_valid is True
    assert result.payload is not None
    assert result.payload["specVersion"] == "0.1"


# --- decompression-bomb bounds --------------------------------------------------------

def test_bounded_inflate_roundtrips_normal_data() -> None:
    data = b"the quick brown fox " * 500
    assert _bounded_inflate(zlib.compress(data)) == data


def test_bounded_inflate_rejects_bomb() -> None:
    bomb = zlib.compress(b"A" * (MAX_PAYLOAD_BYTES + 1000))  # tiny compressed, huge inflated
    assert len(bomb) < MAX_PAYLOAD_BYTES  # the compressed side alone would pass a naive check
    with pytest.raises(PayloadTooLargeError):
        _bounded_inflate(bomb)


def test_read_rejects_decompression_bomb(base_pdf: bytes) -> None:
    out = embed(base_pdf, _sample(), asserted_date=FIXED_DATE)
    with pikepdf.open(io.BytesIO(out)) as pdf:
        stream = _find_ef_stream(pdf)
        assert stream is not None
        stream.write(
            zlib.compress(b"A" * (MAX_PAYLOAD_BYTES + 1000)),
            filter=pikepdf.Name.FlateDecode,
        )
        buf = io.BytesIO()
        pdf.save(buf)
        bomb_pdf = buf.getvalue()
    with pytest.raises(PayloadTooLargeError):
        read(bomb_pdf)
