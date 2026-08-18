"""Cross-implementation round-trip ([OM-VEC-002]), Track A side.

Reads the PDFs the JS writer produced (via js/scripts/crossimpl.mjs, path in
``OPENOM_XIMPL_DIR``) and proves the JS-embedded payload is both detectable by the Python
reader (wire-format interop) and byte-identical to Python's own canonicalization (no fork).

Skipped unless ``OPENOM_XIMPL_DIR`` is set, so the default suite runs without Node.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pikepdf
import pytest

from openom_core.canonical import hash_bytes, payload_hash
from openom_core.embed import read

pytestmark = pytest.mark.cross_impl

XIMPL_DIR = os.environ.get("OPENOM_XIMPL_DIR")
ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "spec" / "vectors"


def _names() -> list[str]:
    manifest = json.loads((VECTORS / "manifest.json").read_text(encoding="utf-8"))
    return [v["name"] for v in manifest["vectors"]]


@pytest.mark.skipif(not XIMPL_DIR, reason="OPENOM_XIMPL_DIR not set (run via the cross-impl job)")
@pytest.mark.parametrize("name", _names())
def test_js_embedded_read_by_python(name: str) -> None:
    pdf_path = Path(XIMPL_DIR or "") / f"{name}.pdf"
    if not pdf_path.exists():
        pytest.skip(f"missing JS-embedded PDF: {pdf_path}")
    data = pdf_path.read_bytes()
    payload = json.loads((VECTORS / "payloads" / f"{name}.json").read_text(encoding="utf-8"))

    result = read(data)
    assert result.present is True, "Python reader did not detect the JS-embedded payload"
    assert result.hash_valid is True, "JS XMP marker not verifiable by the Python reader"

    # Byte-identity: the exact bytes JS stored hash (per Python) to Python's own payload hash.
    with pikepdf.open(io.BytesIO(data)) as pdf:
        stored = pdf.attachments["om.json"].get_file().read_bytes()
    assert hash_bytes(stored) == payload_hash(payload), "canonical byte fork between JS and Python"


@pytest.mark.skipif(not XIMPL_DIR, reason="OPENOM_XIMPL_DIR not set (run via the cross-impl job)")
@pytest.mark.parametrize("producer", ["producer-native", "producer-hybrid", "producer-scanned"])
def test_js_embed_onto_producer_bases_read_by_python(producer: str) -> None:
    """#131: JS embed onto structurally-diverse producer PDFs (object-stream / linearized /
    image-only) must be Python-readable and byte-identical — not just onto a blank page."""
    pdf_path = Path(XIMPL_DIR or "") / f"{producer}.pdf"
    if not pdf_path.exists():
        pytest.skip(f"missing JS-embedded producer PDF: {pdf_path}")
    data = pdf_path.read_bytes()
    payload = json.loads((VECTORS / "payloads" / "sample-stnl.json").read_text(encoding="utf-8"))
    result = read(data)
    assert result.present is True, f"{producer}: Python reader missed the JS-embedded payload"
    assert result.hash_valid is True, f"{producer}: JS XMP marker not verifiable by Python"
    with pikepdf.open(io.BytesIO(data)) as pdf:
        stored = pdf.attachments["om.json"].get_file().read_bytes()
    assert hash_bytes(stored) == payload_hash(payload), f"{producer}: canonical byte fork"
