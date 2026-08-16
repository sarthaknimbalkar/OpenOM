"""Survival ([OM-DoD-001](c)): the payload hash is invariant after >=3 upload->download
round-trips across >=2 storage backends. A byte-preserving store is the common case; a
re-serializing CDN (re-saves the PDF) is the adversarial one — the payload must survive both.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pikepdf

from openom_core.canonical import payload_hash
from openom_core.embed import embed, read

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _blank() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _filesystem_backend(data: bytes, tmp: Path, i: int) -> bytes:
    """Byte-preserving store (S3/R2/local): write then read back verbatim."""
    p = tmp / f"rt_{i}.pdf"
    p.write_bytes(data)
    return p.read_bytes()


def _reserialize_backend(data: bytes, tmp: Path, i: int) -> bytes:
    """Adversarial store: a CDN/optimizer that re-serializes the PDF on the way through."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, recompress_flate=True)
        return buf.getvalue()


_BACKENDS: list[Callable[[bytes, Path, int], bytes]] = [_filesystem_backend, _reserialize_backend]


def test_survival_across_backends_and_roundtrips(tmp_path: Path) -> None:
    sample = _sample()
    expected = payload_hash(sample)
    data = embed(_blank(), sample, asserted_date="2026-08-15")
    assert read(data).hash_valid is True

    i = 0
    for _roundtrip in range(3):  # >= 3 round-trips
        for backend in _BACKENDS:  # >= 2 storage backends
            data = backend(data, tmp_path, i)
            i += 1
            result = read(data)
            assert result.present is True, f"payload lost at step {i}"
            assert result.hash_valid is True, f"integrity broken at step {i}"
            assert payload_hash(result.payload) == expected, f"payload hash drifted at step {i}"
