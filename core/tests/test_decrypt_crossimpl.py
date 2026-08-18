"""#132: cross-implementation decryption agreement. Author-mode decryption is JS-only
(js/src/decrypt.ts, a hand-written AES impl); the Python core relies on pikepdf. Both MUST recover
the SAME plaintext from the same empty-password AES fixtures — else a broker decrypting in-browser
and a server decrypting via the CLI would see different content. This anchors both to the known
plaintext in js/test/fixtures/enc-fixtures.json (the JS side asserts the same in decrypt.test.ts): a
committed, corpus-free cross-check complementing the dev-only pikepdf render oracle."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pymupdf
import pytest

FIX = Path(__file__).resolve().parents[2] / "js" / "test" / "fixtures"
KNOWN = json.loads((FIX / "enc-fixtures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["enc-aes128.pdf", "enc-aes256.pdf"])
def test_pikepdf_and_js_recover_the_same_plaintext(name: str) -> None:
    # Python decrypts via pikepdf (empty user password) -> save cleartext -> extract text + outline.
    with pikepdf.open(FIX / name) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
    doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    outline = doc.get_toc()
    doc.close()
    # The SAME known plaintext the JS decryptPdf test asserts (both impls agree on the cleartext).
    assert KNOWN["text"] in text
    assert any(KNOWN["bookmark"] in row[1] for row in outline), "bookmark title not recovered"
