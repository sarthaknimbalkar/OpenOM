#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate the committed signed-PDF fixture for the incremental-embed gate (#3 [OM-PDF-006]).

A full-rewrite embed invalidates a byte-range digital signature; embed() detects a signed input and
appends the payload via an incremental-update save instead, so the signed bytes stay intact. Proving
that needs a genuinely-signed PDF. This produces one with a self-signed approval signature.

pyhanko + cryptography are needed only to *make* the fixture (not to run the test, and not a core
dependency) - install them ad hoc, like make-enc-fixtures.py. Run with the repo venv:
    .venv/Scripts/python.exe core/tests/fixtures/gen_signed_fixture.py

The output (``signed-approval.pdf``) is committed. The test proves signature preservation by
byte-range integrity: an incremental append that preserves the whole original as a byte-exact prefix
cannot alter any bytes the /ByteRange covers.
"""

from __future__ import annotations

import datetime
import io
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent / "signed-approval.pdf"


def _key_cert_files() -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "openOM test signer")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(key, hashes.SHA256())
    )
    kf = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    kf.write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    kf.close()
    cf = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    cf.write(cert.public_bytes(serialization.Encoding.PEM))
    cf.close()
    return kf.name, cf.name


def make_signed_pdf() -> bytes:
    import pymupdf
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Signed offering memorandum (fixture)")
    src = doc.tobytes()
    doc.close()

    signer = signers.SimpleSigner.load(*_key_cert_files())
    writer = IncrementalPdfFileWriter(io.BytesIO(src))
    fields.append_signature_field(writer, fields.SigFieldSpec(sig_field_name="Sig1"))
    out = io.BytesIO()
    signers.PdfSigner(
        signers.PdfSignatureMetadata(field_name="Sig1"), signer=signer
    ).sign_pdf(writer, output=out)
    return out.getvalue()


if __name__ == "__main__":
    OUT.write_bytes(make_signed_pdf())
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
