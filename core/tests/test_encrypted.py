"""Password-protected PDFs must refuse cleanly (OM-IO-011), never crash (round-3 blocker).

A real user-password PDF can't be opened; read() returns an encrypted ReadResult and the pymupdf
verbs raise EncryptedPdfError - both mapped to a clean OM-IO-011 by the CLI/MCP guards, never a
traceback or a raw pikepdf.PasswordError out of a tool.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest

from openom_core.embed import read
from openom_core.errors import EncryptedPdfError
from openom_core.images import extract_images
from openom_core.inspect import inspect
from openom_core.text import extract_text

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _password_pdf() -> bytes:
    buf = io.BytesIO()
    with pikepdf.open(SPEC / "assets" / "openom-sample.pdf") as p:
        p.save(buf, encryption=pikepdf.Encryption(user="secret", owner="secret", R=6))
    return buf.getvalue()


def test_read_returns_encrypted_state_not_a_raise() -> None:
    r = read(_password_pdf())
    assert r.encrypted is True
    assert r.present is False and r.payload is None


def test_pymupdf_verbs_raise_typed_encrypted_error(tmp_path: Path) -> None:
    data = _password_pdf()
    for fn in (inspect, extract_text):
        with pytest.raises(EncryptedPdfError):
            fn(data)
    with pytest.raises(EncryptedPdfError):
        extract_images(data, out_dir=tmp_path)
