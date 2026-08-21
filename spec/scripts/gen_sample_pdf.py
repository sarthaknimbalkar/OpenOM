#!/usr/bin/env python3
"""Generate the public sample openOM PDF: a one-page mock OM that LOOKS like a real offering
memorandum and carries a real, broker-asserted openOM payload (embedded via the tested core).

WHY: the landing + /verify/ let a visitor *see* what "a PDF with openOM data" is - download this,
open it (looks like an OM), then drop it back into /verify/ and watch the embedded data verify.

Committed artifact (spec/assets/openom-sample.pdf), mirrored to site/sample/ by gen_site.py. Uses
the same sample payload as the fixtures. Deterministic (fixed asserted date). Regenerate:
    python spec/scripts/gen_sample_pdf.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import fitz  # PyMuPDF (a core dep)
from openom_core.embed import embed

SPEC = Path(__file__).resolve().parent.parent
SAMPLE = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
OUT = SPEC / "assets" / "openom-sample.pdf"

INK = (0.09, 0.10, 0.13)
SOFT = (0.29, 0.32, 0.38)
NAVY = (0.06, 0.11, 0.19)


def _render_page() -> bytes:
    """A single diegetic OM page (US Letter). Plain, print-like - the point is the embedded data."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    x = 64.0
    page.insert_text((x, 92), "OFFERING MEMORANDUM", fontname="courier", fontsize=10, color=SOFT)
    page.insert_text(
        (x, 128), "Example Retail - Single-Tenant Net Lease",
        fontname="helvetica-bold", fontsize=22, color=INK,
    )
    page.insert_text(
        (x, 150), "1000 Example Rd - Sampleville, MI 48000",
        fontname="courier", fontsize=11, color=SOFT,
    )
    page.draw_rect(fitz.Rect(x, 172, 548, 262), color=NAVY, fill=NAVY)
    page.insert_text((x + 12, 250), "PROPERTY PHOTO", fontname="courier", fontsize=9,
                     color=(0.7, 0.75, 0.82))

    rows = [
        ("ASKING PRICE", "$1,850,000"),
        ("CAP RATE", "6.25%"),
        ("NOI (IN-PLACE)", "$115,625"),
        ("TENANT", "Example Retail Stores, LLC"),
        ("LEASE TYPE", "Absolute NNN"),
        ("LEASE EXPIRATION", "April 30, 2034"),
        ("OPTIONS", "4 x 5 Years"),
    ]
    y = 300.0
    for label, value in rows:
        page.insert_text((x, y), label, fontname="courier", fontsize=9.5, color=SOFT)
        page.insert_text((x + 240, y), value, fontname="helvetica-bold", fontsize=12, color=INK)
        page.draw_line((x, y + 10), (548, y + 10), color=(0.86, 0.86, 0.83), width=0.6)
        y += 34
    page.insert_text(
        (x, y + 16), "EXAMPLE NET LEASE ADVISORS - CONFIDENTIAL - SAMPLE",
        fontname="courier", fontsize=9, color=(0.63, 0.61, 0.53),
    )
    note = (
        "This PDF carries an embedded, broker-asserted openOM data payload. It looks identical to a"
        " normal OM,\nbut any AI assistant or the verifier at openom.app/verify can read the whole"
        " deal in one call."
    )
    page.insert_textbox(
        fitz.Rect(x, y + 44, 548, y + 96), note, fontname="helvetica", fontsize=10, color=SOFT,
    )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def main() -> None:
    pdf = embed(_render_page(), SAMPLE, asserted_date=str(SAMPLE["assertedDate"]))
    OUT.write_bytes(pdf)
    print(f"wrote {OUT} ({len(pdf)} bytes)")


if __name__ == "__main__":
    main()
