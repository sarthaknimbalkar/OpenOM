#!/usr/bin/env python
"""Generate synthetic empty-user-password encrypted PDFs for the #4 decrypt tests.

Committed for reproducibility. Run with the repo venv:  .venv/Scripts/python.exe js/scripts/make-enc-fixtures.py

Each fixture has a known text string on page 1 (exercises STREAM decryption) and one outline/bookmark
whose title is a known string (exercises STRING decryption). All are encrypted with an EMPTY user
password + a nonempty owner password (permission encryption — the real-corpus case):
  enc-aes128.pdf  V4/R4  AESV2 (AES-128)
  enc-aes256.pdf  V5/R6  AESV3 (AES-256)
  enc-rc4.pdf     V2/R4  RC4    (out-of-scope control -> decryptPdf must return null)
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pymupdf

ENC_TEXT = "OPENOM-ENC-FIXTURE-PLAINTEXT"
ENC_BOOKMARK = "openOM encrypted bookmark title"
OUT = Path(__file__).resolve().parent.parent / "test" / "fixtures"


def build_plaintext_pdf() -> bytes:
    """A minimal 1-page PDF with ENC_TEXT drawn on page 1 and one ENC_BOOKMARK outline entry."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((40, 100), ENC_TEXT, fontsize=14)
    doc.set_toc([[1, ENC_BOOKMARK, 1]])
    data = doc.tobytes()
    doc.close()
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plain = build_plaintext_pdf()

    variants = [
        ("enc-aes128", pikepdf.Encryption(owner="owner", user="", aes=True, R=4)),
        ("enc-aes256", pikepdf.Encryption(owner="owner", user="", aes=True, R=6)),
        # RC4 control: pikepdf refuses to encrypt metadata without AES, so opt out explicitly.
        ("enc-rc4", pikepdf.Encryption(owner="owner", user="", aes=False, R=4, metadata=False)),
    ]
    # Force compressed object streams so the fixtures mirror real-producer OMs (ObjStm + xref streams) —
    # the structure that a parse-before-decrypt approach silently corrupts. Without this the CI fixtures
    # are unrepresentative and an ObjStm regression slips through green tests (see #4 execution).
    for name, enc in variants:
        with pikepdf.open(io.BytesIO(plain)) as pdf:
            pdf.save(
                OUT / f"{name}.pdf",
                encryption=enc,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        print(f"wrote {name}.pdf")

    (OUT / "enc-fixtures.json").write_text(
        json.dumps({"text": ENC_TEXT, "bookmark": ENC_BOOKMARK}, indent=2) + "\n",
        encoding="utf8",
    )
    print("wrote enc-fixtures.json")


if __name__ == "__main__":
    main()
