# SPDX-License-Identifier: MIT
"""Generate the synthetic demo OM for the M4 process gate ([OM-DoD-005]).

A small, entirely FICTIONAL single-tenant NNN offering memorandum (fictional broker/tenant/address/
APN, no real deal — OM-VEC-017-clean), rendered as human-readable OM copy (NOT JSON) so the
playbook's extraction step is a real reading task. The printed facts correspond to a known-good,
warning-clean openOM payload (see process/example/expected-payload.json). Regenerate with:
    python process/example/build_example.py

Numbers are chosen so the derived payload is internally consistent (validator warning-clean):
  capRate 0.0575 = 143750 / 2500000 · pricePerSF 416.67 = 2500000 / 6000
  rentPSF 23.96 = 143750 / 6000 · 26.35 = 158125 / 6000 · escalation 0.10 = 158125/143750 - 1
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent / "sample-om.pdf"
OUT_SCANNED = Path(__file__).resolve().parent / "sample-om-scanned.pdf"

LINES = [
    ("OFFERING MEMORANDUM", 20, True),
    ("Placeholder Quick Service — Testville, TX", 14, True),
    ("Single-Tenant Net-Leased Investment (Fictional / Example Only)", 11, False),
    ("", 11, False),
    ("Presented by: Dana Sample, Placeholder Retail Advisors | License: TX 000000", 10, False),
    ("", 11, False),
    ("FINANCIAL SUMMARY", 13, True),
    ("Offering Price:        $2,500,000", 11, False),
    ("Cap Rate:              5.75%", 11, False),
    ("Net Operating Income:  $143,750 (in-place, as of 05/31/2026)", 11, False),
    ("Price / SF:            $416.67", 11, False),
    ("Status:                Active", 11, False),
    ("", 11, False),
    ("PROPERTY", 13, True),
    ("Address:     500 Example Blvd, Testville, TX 75000", 11, False),
    ("APN:         R000000", 11, False),
    ("Building:    +/- 6,000 SF", 11, False),
    ("Year Built:  2021", 11, False),
    ("", 11, False),
    ("LEASE ABSTRACT", 13, True),
    ("Tenant:      Placeholder Quick Service, LLC", 11, False),
    ("Guarantor:   Placeholder Brands Inc. (Corporate)", 11, False),
    ("Lease Type:  NNN (Tenant pays all taxes, insurance, and CAM)", 11, False),
    ("Lease Term:  06/01/2021 - 05/31/2031", 11, False),
    ("", 11, False),
    ("RENT SCHEDULE", 13, True),
    ("Period                     Annual Rent    Rent/SF    Increase", 10, False),
    ("06/01/2021 - 05/31/2026    $143,750       $23.96     -", 10, False),
    ("06/01/2026 - 05/31/2031    $158,125       $26.35     10%", 10, False),
    ("", 11, False),
    ("Two (2) five-year renewal options remain.", 10, False),
    ("", 11, False),
    ("This is a fictional example document for openOM testing. Not an offer.", 9, False),
]


def _text_doc() -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    y = 60.0
    for text, size, bold in LINES:
        if text:
            font = "hebo" if bold else "helv"
            page.insert_text((54, y), text, fontsize=size, fontname=font)
        y += size + 6
    return doc


def build() -> None:
    """The native (text-layer) demo OM — the default extraction target."""
    doc = _text_doc()
    doc.save(OUT)
    doc.close()
    print(f"wrote {OUT}")


def build_scanned() -> None:
    """An image-only (no text layer) version of the same OM — classifies as ``scanned``, exercising
    the playbook's vision/OCR branch. Rasterize the text page, then place ONLY that image."""
    src = _text_doc()
    pix = src[0].get_pixmap(dpi=150)
    src.close()
    out = pymupdf.open()
    page = out.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pix)
    out.save(OUT_SCANNED)
    out.close()
    print(f"wrote {OUT_SCANNED}")


if __name__ == "__main__":
    build()
    build_scanned()
