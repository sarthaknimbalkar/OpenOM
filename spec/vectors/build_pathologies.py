# SPDX-License-Identifier: MIT
"""Generate the committed pathology golden PDFs (M2 #11).

Three real-world-nasty base documents, each carrying an embedded `om.json`, committed under
`spec/vectors/pathologies/` so BOTH implementations prove they read a payload out of them
(Python producer → pikepdf + pdf-lib consumers). This complements the JS-producer goldens in
`spec/vectors/pdfs/`. Regenerate with:  python -m spec.vectors.build_pathologies

The check is payload-fidelity (the extracted `om.json` bytes), never PDF-byte identity, so
PDF-level nondeterminism (ids/timestamps) does not matter.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pymupdf
from openom_core.embed import embed

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent
OUT = HERE / "pathologies"
DATE = "2026-08-15"

_SAMPLE = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
_MINIMAL = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "specVersion": "0.1",
    "assertedBy": {"broker": "A", "brokerage": "B", "license": "C"},
    "assertedDate": "2026-08-16",
    "meta": {"supersedes": None},
}


def _blank_base() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(300, 300))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _scanned_base() -> bytes:
    """An image-only page (no text layer) — classifies as `scanned`."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300))
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(pymupdf.Rect(0, 0, 300, 300), pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


def _encrypt(pdf_bytes: bytes) -> bytes:
    """Re-save an embedded PDF as an empty-password encrypted document (the 'secured' export).

    Encryption is applied AFTER embed so the committed golden is genuinely encrypted while still
    carrying the `/AF` attachment; preserving encryption THROUGH embed is a separate concern (#4).
    """
    with pikepdf.open(io.BytesIO(pdf_bytes)) as doc:
        buf = io.BytesIO()
        doc.save(buf, encryption=pikepdf.Encryption(owner="", user=""))
        return buf.getvalue()


# name -> (base bytes, payload embedded, post-processor). Expectations live in manifest.json.
_CASES = {
    "empty-payload": (_blank_base, _MINIMAL, None),
    "scanned": (_scanned_base, _SAMPLE, None),
    "encrypted": (_blank_base, _SAMPLE, _encrypt),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    manifest = {
        "specVersion": "0.1",
        "description": "Pathology golden PDFs (#11): both implementations MUST extract the "
        "embedded payload. Python producer; pikepdf + pdf-lib consumers.",
        "cases": [],
    }
    for name, (base_fn, payload, post) in _CASES.items():
        pdf = embed(base_fn(), payload, asserted_date=DATE)
        if post is not None:
            pdf = post(pdf)
        (OUT / f"{name}.pdf").write_bytes(pdf)
        (OUT / f"{name}.expected.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        entry = {"name": name, "pdf": f"{name}.pdf", "expected": f"{name}.expected.json"}
        if name == "scanned":
            entry["class"] = "scanned"
        if name == "encrypted":
            entry["encrypted"] = True
        manifest["cases"].append(entry)  # type: ignore[attr-defined]
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(_CASES)} pathology goldens to {OUT}")


if __name__ == "__main__":
    main()
