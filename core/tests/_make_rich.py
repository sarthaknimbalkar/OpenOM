"""Test helper: a synthetic PDF exercising the structures embedding must NOT disturb —
real text, an internal GoTo link, an external URI link, bookmarks (TOC), and a raster image.
Lets the non-destructive proof run in CI without the confidential corpus.
"""

from __future__ import annotations

import pymupdf


def make_rich_pdf() -> bytes:
    doc = pymupdf.open()
    try:
        p1 = doc.new_page(width=612, height=792)
        p1.insert_text((72, 72), "Offering memorandum — page one. " * 10, fontsize=11)
        p2 = doc.new_page(width=612, height=792)
        p2.insert_text((72, 72), "Page two: rent schedule and financials.", fontsize=11)

        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 64))
        pix.set_rect(pix.irect, (30, 120, 200))
        p2.insert_image(pymupdf.Rect(72, 120, 200, 248), pixmap=pix)

        # Re-load page 0 fresh: page handles can go stale after other pages are mutated.
        p1 = doc.load_page(0)
        p1.insert_link(
            {
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(72, 300, 260, 320),
                "page": 1,
                "to": pymupdf.Point(72, 72),
            }
        )
        p1.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(72, 330, 260, 350),
                "uri": "https://vervelio.com",
            }
        )
        doc.set_toc([[1, "Overview", 1], [1, "Financials", 2]])
        return doc.tobytes()
    finally:
        doc.close()
